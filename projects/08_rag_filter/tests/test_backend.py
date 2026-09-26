"""Project 08, offline: retriever, keep policy, per-chunk isolation, parallel judges, gold isolation, graph."""

import importlib
import time

import pytest

exp = importlib.import_module("projects.08_rag_filter.experiment")
jev_client = importlib.import_module("projects.08_rag_filter.jev_client")
llm = importlib.import_module("projects.08_rag_filter.llm")
policy = importlib.import_module("projects.08_rag_filter.policy")
retriever = importlib.import_module("projects.08_rag_filter.retriever")
openrouter = importlib.import_module("shared.openrouter")


def test_retriever_is_deterministic_and_returns_k():
    a, b = retriever.retrieve("How long do I have to return unused items?", 6), \
        retriever.retrieve("How long do I have to return unused items?", 6)
    assert a == b and len(a) == 6 and a[0]["id"] == "refunds-window"


def test_every_gold_chunk_is_retrievable():
    """If the retriever never returns the relevant chunk, no filter can be blamed for missing it."""
    for row in exp.DATASET:
        got = {c["id"] for c in retriever.retrieve(row["input"]["question"], 6)}
        assert set(row["input"]["relevant"]) <= got, row["text"]


J = {"id": "c", "useful": 0.9, "injection": 0.02, "sensitive": 0.02}


@pytest.mark.parametrize("j,kept", [
    (J, True),
    (J | {"useful": 0.3}, False),
    (J | {"injection": 0.95}, False),       # useful AND an injection: dropped, safety rule comes first
    (J | {"sensitive": 0.90}, False),
    (J | {"sensitive": 0.60}, True),        # unsure about sensitivity is not enough to drop
])
def test_verdict(j, kept):
    assert policy.verdict(j)[0] is kept


def test_keep_orders_by_usefulness_and_caps():
    js = [J | {"id": f"c{i}", "useful": 0.5 + i / 10} for i in range(5)]
    assert policy.keep(js, 3) == ["c4", "c3", "c2"]


@pytest.mark.parametrize("kept,gold,pr", [
    (["a", "b"], ["a"], (0.5, 1.0)), ([], ["a"], (None, 0.0)), (["a"], [], (0.0, None)), ([], [], (None, None))])
def test_precision_recall(kept, gold, pr):
    assert policy.precision_recall(kept, gold) == pr


def call(cost=0.00001, ms=100.0):
    return {"latency_ms": ms, "input_tokens": 100, "output_tokens": 10, "cost_usd": cost}


@pytest.fixture
def offline(monkeypatch):
    """Fakes at the network edge. Records every Jev state and every LLM input."""
    rec = {"jev": [], "llm": []}
    bad = {"evil-note": {"injection": 0.97}, "hr-salaries": {"sensitive": 0.95}}

    def decide(state, questions):
        rec["jev"].append(state)
        usage = {"input_tokens": 200, "output_tokens": 0, "cost": 0.000008}
        if "correct" in questions:
            return {"answers": {"correct": {"noul": 0.9}}, "usage": usage, "id": "g"}, 50.0
        cid = next(c["id"] for c in retriever.CORPUS if c["text"] == state["chunk"])
        a = {"useful": 0.9 if cid in ("refunds-window", "refunds-timing") else 0.1, "injection": 0.02,
             "sensitive": 0.02} | bad.get(cid, {})
        return {"answers": {k: {"noul": v} for k, v in a.items()}, "model": "typesafe/jev-1.13-20260917",
                "usage": usage, "id": "j"}, 80.0

    monkeypatch.setattr(openrouter, "decide", decide)
    monkeypatch.setattr(llm, "pick_chunks", lambda q, chunks: (rec["llm"].append((q, chunks)) or
                                                               ([c["id"] for c in chunks][:4], call())))
    monkeypatch.setattr(llm, "answer", lambda q, chunks: (rec["llm"].append((q, chunks)) or
                                                          (f"answer from {[c['id'] for c in chunks]}", call())))
    return rec


def test_offline_graph(offline):
    r = exp.run_experiment(exp.EXAMPLES["Stale policy nearby"])
    jev = r.runs["jev"]
    assert jev.raw["kept"] == ["refunds-window"] and (jev.raw["precision"], jev.raw["recall"]) == (1.0, 1.0)
    assert r.runs["all_chunks"].raw["kept"] == r.runs["all_chunks"].raw["retrieved"]
    assert jev.cost_usd == pytest.approx(6 * 0.000008 + 0.00001)   # 6 judges + 1 answer ...
    assert jev.raw["grade_cost"] == 0.000008                        # ... grading kept apart
    assert jev.latency_ms == pytest.approx(80.0 + 100.0)            # parallel judges count once
    assert r.trace_url is None


def test_each_jev_state_holds_exactly_one_chunk(offline):
    exp.run_experiment(exp.EXAMPLES["Stale policy nearby"])
    judged = [s for s in offline["jev"] if "chunk" in s]
    assert len(judged) == 6 and all(set(s) == {"question", "chunk", "source"} for s in judged)


def test_injection_and_private_chunks_never_reach_the_jev_answer(offline):
    r = exp.run_experiment(exp.EXAMPLES["Injection bait"])
    assert "evil-note" in r.runs["jev"].raw["retrieved"] and "evil-note" not in r.runs["jev"].raw["kept"]
    assert "hr-salaries" not in r.runs["jev"].raw["kept"]
    assert r.runs["jev"].raw["verdicts"]["evil-note"].startswith("injection")
    assert "evil-note" in r.runs["all_chunks"].raw["kept"]          # plain RAG passes it straight on


def test_nothing_kept_means_no_answer_and_no_llm_call(offline):
    exp.run_experiment(exp.EXAMPLES["Private data"])
    jev_answer_calls = [chunks for q, chunks in offline["llm"] if chunks == []]
    assert jev_answer_calls == []                                   # jev never called answer() with nothing


def test_gold_never_reaches_a_filter_or_answerer(offline):
    inp = exp.EXAMPLES["Stale policy nearby"]
    exp.run_experiment(inp)
    seen = str(offline["llm"]) + str([s for s in offline["jev"] if "chunk" in s])
    assert inp["rubric"] not in seen and "relevant" not in seen


def test_judges_run_in_parallel(monkeypatch, offline):
    real = jev_client.judge_chunk

    def slow(q, chunk):
        time.sleep(0.3)
        return real(q, chunk)
    monkeypatch.setattr(jev_client, "judge_chunk", slow)
    t0 = time.perf_counter()
    exp.run_experiment(exp.EXAMPLES["Stale policy nearby"])
    assert time.perf_counter() - t0 < 1.2    # 6 × 0.3 s one after another would be 1.8 s
