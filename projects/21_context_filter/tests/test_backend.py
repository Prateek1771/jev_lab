"""Project 21, offline: items judged one per call and in parallel, only kept items reach the answer, gold and
rubric stay out, and the keyword filter's blind spots."""

import importlib
import time

import pytest

exp = importlib.import_module("projects.21_context_filter.experiment")
openrouter = importlib.import_module("shared.openrouter")


@pytest.fixture
def offline(monkeypatch):
    rec = {"judged": [], "contexts": []}
    needed = {"#412", "#418"}

    def decide(state, q):
        if "correct" in q:
            return {"answers": {"correct": {"noul": 0.9}}, "usage": {"cost": 0.00001}, "id": "g"}, 40.0
        rec["judged"].append(state)
        p = 0.9 if state["item"]["id"] in needed else 0.1
        return {"answers": {"needed": {"noul": p}}, "model": "typesafe/jev-1.13-20260917",
                "usage": {"input_tokens": 120, "output_tokens": 0, "cost": 0.000005}, "id": "j"}, 60.0
    monkeypatch.setattr(openrouter, "decide", decide)
    from langchain_core.messages import AIMessage

    def metered(name, llm, msgs):
        rec["contexts"].append((name, msgs[-1].content))
        return AIMessage("#412 and #418 block 2.4."), {"model": "m", "latency_ms": 500.0, "input_tokens": len(msgs[-1].content) // 4,
                                                       "output_tokens": 20, "cost_usd": 0.00003, "finish_reason": "stop"}
    monkeypatch.setattr(exp, "chat_model", lambda *a: None)
    monkeypatch.setattr(exp, "metered_call", metered)
    return rec


def test_one_item_per_call_and_only_kept_items_answer(offline):
    inp = exp.EXAMPLES["Release blockers"]
    r = exp.run_experiment(inp)
    assert len(offline["judged"]) == 30 and all(set(s) == {"question", "item"} for s in offline["judged"])
    j = r.runs["jev"]
    assert j.raw["kept"] == ["#412", "#418"] and (j.raw["precision"], j.raw["recall"]) == (1.0, 1.0)
    assert j.raw["context_tokens"] < r.runs["everything"].raw["context_tokens"]
    seen = str(offline["contexts"]) + str(offline["judged"])
    assert inp["rubric"] not in seen and "'gold'" not in seen
    assert r.runs["llm_summary"].raw["kept"] is None and len([n for n, _ in offline["contexts"] if n == "llm.summarize"]) == 1


def test_judges_run_in_parallel(monkeypatch, offline):
    real = openrouter.decide

    def slow(state, q):
        if "item" in state:
            time.sleep(0.05)
        return real(state, q)
    monkeypatch.setattr(openrouter, "decide", slow)
    t0 = time.perf_counter()
    exp.run_experiment(exp.EXAMPLES["Why did CI fail"])
    assert time.perf_counter() - t0 < 1.0     # 26 × 0.05 s one after another would be 1.3 s


def test_keyword_filter_is_blind_to_meaning():
    """grep keeps items that share a word and drops the ones that say it differently."""
    import json
    import re
    losses = 0
    for row in exp.DATASET:
        inp = row["input"]
        words = {w for w in re.findall(r"[a-z0-9.]+", inp["question"].lower()) if len(w) > 3 and w not in exp.STOP}
        kept = {it["id"] for it in exp.OUTPUTS[inp["output"]] if words & set(re.findall(r"[a-z0-9.]+", json.dumps(it).lower()))}
        losses += bool(set(inp["gold"]) - kept) or len(kept) > 3 * max(len(inp["gold"]), 1)
    assert losses >= 6
