"""Project 09, offline: ranking maths, Jev ordering, isolation, parallel scores, gold isolation, the graph,
and that the dataset actually gives a reranker something to fix."""

import importlib
import time

import pytest

from config import settings

exp = importlib.import_module("projects.09_rag_reranker.experiment")
jev_client = importlib.import_module("projects.09_rag_reranker.jev_client")
llm = importlib.import_module("projects.09_rag_reranker.llm")
ranking = importlib.import_module("projects.09_rag_reranker.ranking")
retriever = importlib.import_module("projects.09_rag_reranker.retriever")
openrouter = importlib.import_module("shared.openrouter")


def test_ndcg_perfect_and_worse():
    gold = {"a": 2, "b": 1}
    assert ranking.ndcg_at_k(["a", "b", "c"], gold, 3) == pytest.approx(1.0)
    # DCG = 0 + 1/log2(3) + 3/log2(4) = 2.1309; ideal = 3 + 1/log2(3) = 3.6309
    assert ranking.ndcg_at_k(["c", "b", "a"], gold, 3) == pytest.approx(0.5869, abs=1e-4)
    assert ranking.ndcg_at_k(["c", "d", "e", "a"], gold, 3) == 0.0          # the answer fell out of the top 3
    assert ranking.ndcg_at_k(["a"], {}, 3) is None                           # nothing relevant: nothing to measure


def test_mrr():
    assert ranking.mrr(["x", "y", "a"], {"a": 2}) == pytest.approx(1 / 3)
    assert ranking.mrr(["x"], {"a": 2}) == 0.0                              # retrieved nothing that answers
    assert ranking.mrr(["a"], {"a": 1}) is None                             # no chunk directly answers


def test_jev_order_sorts_by_score_and_breaks_ties_by_retriever_rank():
    scores = [{"id": "a", "score": 1.0, "p_top": 0.5}, {"id": "b", "score": 1.0, "p_top": 0.0},
              {"id": "c", "score": 1.9, "p_top": 0.9}]
    assert ranking.jev_order(scores, ["b", "a", "c"]) == ["c", "b", "a"]        # b before a: retriever tie-break
    assert ranking.jev_order(scores, ["b", "a", "c"], key="p_top") == ["c", "a", "b"]   # same scores, other key


def test_the_dataset_gives_a_reranker_work():
    """If the retriever already put the answer first everywhere, reranking would have nothing to fix."""
    imperfect = 0
    for row in exp.DATASET:
        got = [c["id"] for c in retriever.retrieve(row["input"]["question"], settings.RERANK_N)]
        gold = row["input"]["gold"]
        assert {cid for cid, g in gold.items() if g == 2} <= set(got), row["text"]   # the answer is retrievable
        n = ranking.ndcg_at_k(got, gold, settings.RERANK_K)
        imperfect += n is not None and n < 1
    assert imperfect >= 10


def test_llm_rank_is_repaired_not_trusted(monkeypatch):
    chunks = [{"id": i, "text": i} for i in ("a", "b", "c")]

    class Fake:
        def with_structured_output(self, *a, **k):
            return self
    monkeypatch.setattr(llm, "chat_model", lambda *a: Fake())
    monkeypatch.setattr(llm, "metered_call", lambda name, runnable, msgs: ({"parsed": {"order": ["c", "zzz", "c"]}}, {}))
    assert llm.rank("q", chunks)[0] == ["c", "a", "b"]   # unknown and duplicate dropped, missing appended in order


def call(cost=0.00001, ms=100.0):
    return {"latency_ms": ms, "input_tokens": 100, "output_tokens": 10, "cost_usd": cost, "finish_reason": "stop"}


@pytest.fixture
def offline(monkeypatch):
    """Fakes at the network edge; records every Jev state and LLM input."""
    rec = {"jev": [], "llm": []}
    direct = {"returns-window": 1.95, "pay-methods": 1.9}

    def decide(state, questions):
        rec["jev"].append(state)
        usage = {"input_tokens": 200, "output_tokens": 0, "cost": 0.000008}
        if "correct" in questions:
            return {"answers": {"correct": {"noul": 0.9}}, "usage": usage, "id": "g"}, 50.0
        cid = next(c["id"] for c in retriever.CORPUS if c["text"] == state["chunk"])
        s = direct.get(cid, 0.4)
        return {"answers": {"relevance": {"score": s, "confidence": 0.8,
                                          "probabilities": {"0": 0.5, "1": 0.3, "2": 0.9 if s > 1.5 else 0.2}}},
                "model": "typesafe/jev-1.13-20260917", "usage": usage, "id": "j"}, 80.0

    monkeypatch.setattr(openrouter, "decide", decide)
    monkeypatch.setattr(llm, "rank", lambda q, chunks: (rec["llm"].append((q, chunks)) or ([c["id"] for c in chunks], call())))
    monkeypatch.setattr(llm, "answer", lambda q, chunks: (rec["llm"].append((q, chunks)) or
                                                          (f"answer from {[c['id'] for c in chunks]}", call())))
    return rec


def test_offline_graph(offline):
    r = exp.run_experiment(exp.EXAMPLES["Buried answer"])
    jev, base = r.runs["jev"], r.runs["retriever_order"]
    assert jev.raw["top"][0] == "returns-window" and jev.raw["mrr"] == 1.0         # Jev pulled the answer up
    assert base.raw["mrr"] == pytest.approx(1 / 5) and base.raw["ndcg"] < jev.raw["ndcg"]
    assert jev.cost_usd == pytest.approx(10 * 0.000008 + 0.00001)                  # 10 scores + 1 answer ...
    assert jev.raw["grade_cost"] == 0.000008                                        # ... grade kept apart
    assert jev.latency_ms == pytest.approx(80.0 + 100.0)                            # parallel scores count once
    assert r.trace_url is None


def test_each_score_state_holds_exactly_one_chunk(offline):
    exp.run_experiment(exp.EXAMPLES["Buried answer"])
    scored = [s for s in offline["jev"] if "chunk" in s]
    assert len(scored) == settings.RERANK_N and all(set(s) == {"question", "chunk", "source"} for s in scored)


def test_gold_never_reaches_a_ranker_or_answerer(offline):
    inp = exp.EXAMPLES["Buried answer"]
    exp.run_experiment(inp)
    seen = str(offline["llm"]) + str([s for s in offline["jev"] if "chunk" in s])
    assert inp["rubric"] not in seen and "gold" not in seen and "'grade'" not in seen


def test_scores_run_in_parallel(monkeypatch, offline):
    real = jev_client.score_chunk

    def slow(q, chunk):
        time.sleep(0.2)
        return real(q, chunk)
    monkeypatch.setattr(jev_client, "score_chunk", slow)
    t0 = time.perf_counter()
    exp.run_experiment(exp.EXAMPLES["Buried answer"])
    assert time.perf_counter() - t0 < 1.2    # 10 × 0.2 s one after another would be 2 s
