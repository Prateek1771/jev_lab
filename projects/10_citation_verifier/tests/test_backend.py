"""Project 10, offline: claim splitting, code checks, the verdict rules, one pair per Jev call, parallel pairs,
no Jev call for what code settles, the graph's costs, and the LLM judge's enum."""

import importlib
import time

import pytest

exp = importlib.import_module("projects.10_citation_verifier.experiment")
claims = importlib.import_module("projects.10_citation_verifier.claims")
jev_client = importlib.import_module("projects.10_citation_verifier.jev_client")
llm = importlib.import_module("projects.10_citation_verifier.llm")
openrouter = importlib.import_module("shared.openrouter")


def test_split_claims():
    got = claims.split_claims("Returns take 30 days [a]. Refunds are free.[b][b]  Shipping costs $4.99. [c][d]\n")
    assert got == [{"text": "Returns take 30 days.", "cites": ["a"]},
                   {"text": "Refunds are free.", "cites": ["b"]},             # duplicate id kept once
                   {"text": "Shipping costs $4.99.", "cites": ["c", "d"]}]     # "$4.99" is not a sentence end
    assert claims.split_claims("No citation here. None here either!") == [
        {"text": "No citation here.", "cites": []}, {"text": "None here either!", "cites": []}]
    # found clicking through the real app: a bare "Yes." made a correct answer "insufficient: uncited"
    assert claims.split_claims("Yes. Returns take 30 days [a].") == [{"text": "Returns take 30 days.", "cites": ["a"]}]
    assert claims.split_claims("No, returns take 30 days [a].")[0]["text"] == "No, returns take 30 days."


def test_code_check():
    ids = {"a", "b"}
    assert claims.code_check({"cites": []}, ids) == "uncited"
    assert claims.code_check({"cites": ["a", "zzz"]}, ids) == "unknown_source"   # one made-up id is enough
    assert claims.code_check({"cites": ["a", "b"]}, ids) is None


@pytest.mark.parametrize("checks, want", [
    ([("supports", 0.9)], "supported"),
    ([("contradicts", 0.9), ("supports", 0.8)], "supported"),     # a stale page next to the current one
    ([("contradicts", 0.9), ("not_addressed", 0.9)], "contradicted"),
    ([("not_addressed", 0.9)], "insufficient"),
    ([("supports", 0.3)], "insufficient"),                        # unsure proves nothing
    ([("contradicts", 0.3), ("supports", 0.2)], "insufficient"),
])
def test_claim_verdict(checks, want):
    assert claims.claim_verdict([{"choice": c, "confidence": p} for c, p in checks]) == want


def test_answer_verdict_worst_claim_wins():
    assert claims.answer_verdict(["supported", "supported"]) == "supported"
    assert claims.answer_verdict(["supported", "insufficient"]) == "insufficient"
    assert claims.answer_verdict(["insufficient", "contradicted", "supported"]) == "contradicted"
    assert claims.answer_verdict([]) == "insufficient"


def test_llm_judge_outside_the_enum_is_invalid(monkeypatch):
    class Fake:
        def with_structured_output(self, *a, **k):
            return self
    monkeypatch.setattr(llm, "chat_model", lambda *a: Fake())
    monkeypatch.setattr(llm, "metered_call", lambda n, r, m: ({"parsed": {"label": "partly", "reason": "x"}}, {}))
    assert llm.judge("q", "a", [])[0] is None
    monkeypatch.setattr(llm, "metered_call", lambda n, r, m: ({"parsed": None}, {}))
    assert llm.judge("q", "a", [])[0] is None


def call(cost=0.00002, ms=300.0):
    return {"model": "m", "latency_ms": ms, "input_tokens": 300, "output_tokens": 20, "cost_usd": cost,
            "finish_reason": "stop"}


@pytest.fixture
def offline(monkeypatch):
    """Fakes at the network edge. The fake Jev 'reads' by looking for the claim's numbers in the source."""
    rec = {"jev": [], "llm": []}

    def decide(state, questions):
        rec["jev"].append(state)
        choice = "contradicts" if "always free" in state["claim"] else "supports"
        return {"answers": {"support": {"choice": choice, "confidence": 0.9, "probabilities": {}}},
                "model": "typesafe/jev-1.13-20260917", "usage": {"input_tokens": 150, "output_tokens": 0,
                                                                 "cost": 0.000006}, "id": "j"}, 80.0

    monkeypatch.setattr(openrouter, "decide", decide)
    monkeypatch.setattr(llm, "judge", lambda q, a, s: (rec["llm"].append((q, a, s)) or ("supported", "ok", call())))
    return rec


def test_offline_graph(offline):
    r = exp.run_experiment(exp.EXAMPLES["One sentence is wrong"])
    jev, judge, trust = r.runs["jev"], r.runs["llm_judge"], r.runs["trust_citations"]
    assert jev.label == "contradicted" and [c["verdict"] for c in jev.raw["claims"]] == ["supported", "contradicted"]
    assert jev.cost_usd == pytest.approx(2 * 0.000006) and jev.latency_ms == 80.0   # 2 pairs, in parallel
    assert "always free" in jev.raw["reason"]
    assert judge.label == "supported" and judge.cost_usd == 0.00002
    assert trust.label == "supported" and trust.cost_usd == 0.0                    # trusting brackets is free
    assert r.trace_url is None


def test_each_jev_call_sees_one_claim_and_one_source(offline):
    exp.run_experiment(exp.EXAMPLES["One sentence is wrong"])
    assert len(offline["jev"]) == 2
    assert all(set(s) == {"claim", "source"} and isinstance(s["source"], str) for s in offline["jev"])


def test_code_settles_without_a_jev_call(offline):
    r = exp.run_experiment(exp.EXAMPLES["Made-up citation"])        # the only claim cites an unknown id
    assert offline["jev"] == [] and r.runs["jev"].label == "insufficient"
    assert r.runs["jev"].cost_usd == 0 and r.runs["jev"].raw["claims"][0]["code"] == "unknown_source"
    assert r.runs["trust_citations"].label == "supported"          # the brackets look fine
    inp = exp.EXAMPLES["Every claim checks out"] | {"answer": "Returns are easy. No citations at all."}
    r = exp.run_experiment(inp)
    assert offline["jev"] == [] and r.runs["jev"].label == r.runs["trust_citations"].label == "insufficient"


def test_pairs_run_in_parallel(monkeypatch, offline):
    real = jev_client.check_pair

    def slow(claim, source):
        time.sleep(0.3)
        return real(claim, source)
    monkeypatch.setattr(jev_client, "check_pair", slow)
    inp = exp.EXAMPLES["Every claim checks out"] | {
        "answer": "A [returns-window][returns-label]. B [returns-window]. C [returns-label]."}
    t0 = time.perf_counter()
    exp.run_experiment(inp)
    assert len(offline["jev"]) == 4 and time.perf_counter() - t0 < 1.0   # 4 × 0.3 s in a row would be 1.2 s


def test_the_dataset_needs_more_than_code_and_brackets():
    """If code checks alone (or trusting brackets) got most rows right, the project would measure nothing."""
    by_code = trusted = 0
    for row in exp.DATASET:
        inp = row["input"]
        ids = {s["id"] for s in inp["sources"]}
        cs = claims.split_claims(inp["answer"])
        codes = [claims.code_check(c, ids) for c in cs]
        by_code += all(codes) and row["label"] == "insufficient"
        trusted += ("supported" if all(c["cites"] for c in cs) else "insufficient") == row["label"]
        assert all(set(c["cites"]) & ids or claims.code_check(c, ids) for c in cs)
    assert by_code <= 3 and trusted <= 11


def test_safety_spec_names_its_three_rows():
    assert {exp.SAFETY["unsafe"], exp.SAFETY["safe"]} <= set(exp.LABELS) and len(exp.SAFETY["names"]) == 3
