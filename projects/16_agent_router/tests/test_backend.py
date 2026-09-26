"""Project 16, offline: two-level routing (the second Choice only offers the chosen agent's tools), tool
accuracy, gold never reaching a model, the flat agent's parsing, and that keywords are not enough."""

import importlib
import re

import pytest

exp = importlib.import_module("projects.16_agent_router.experiment")
agents = importlib.import_module("projects.16_agent_router.agents")
openrouter = importlib.import_module("shared.openrouter")


def test_tree_is_consistent():
    assert len(agents.TOOL_AGENT) == 12 and len(exp.FLAT_TOOLS) == 12 and len(exp.PAIRS) == 12
    assert {r["input"]["tool"] for r in exp.DATASET} == set(agents.TOOL_AGENT)          # every tool, twice
    assert all(r["label"] == agents.TOOL_AGENT[r["input"]["tool"]] for r in exp.DATASET)


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def with_structured_output(self, *a, **k):
        return self

    def bind_tools(self, *a, **k):
        return self


@pytest.fixture
def offline(monkeypatch):
    seen = []

    def decide(state, q):
        seen.append((state, q))
        name = next(iter(q))
        choice = "coding" if name == "agent" else "search_code"
        return {"id": "d", "model": "typesafe/jev-1.13-20260917",
                "answers": {name: {"choice": choice, "confidence": 0.8 if name == "agent" else 0.6, "probabilities": {}}},
                "usage": {"input_tokens": 150, "output_tokens": 0, "cost": 0.000006}}, 70.0
    monkeypatch.setattr(openrouter, "decide", decide)
    from langchain_core.messages import AIMessage

    def metered(name, llm, msgs):
        call = {"model": "m", "latency_ms": 900.0, "input_tokens": 1200 if "flat" in name else 400,
                "output_tokens": 10, "cost_usd": 0.00005}
        if "flat" in name:
            return AIMessage("", tool_calls=[{"name": "issue_refund", "args": {"input": "x"}, "id": "1"}]), call
        return {"parsed": {"route": "coding/search_code"}}, call
    monkeypatch.setattr(exp, "chat_model", lambda *a: FakeLLM(None))
    monkeypatch.setattr(exp, "metered_call", metered)
    return seen


def test_two_levels_second_offers_only_that_agents_tools(offline):
    r = exp.run_experiment(exp.EXAMPLES["'Refund' in a code question"])
    (s1, q1), (s2, q2) = offline
    assert set(s1) == {"request"} and set(q1["agent"]["criteria"]) == set(agents.AGENTS)
    assert s2 == {"request": s1["request"], "agent": "coding"} and set(q2["tool"]["criteria"]) == set(agents.AGENTS["coding"][1])
    j = r.runs["jev"]
    assert (j.label, j.raw["tool"], j.raw["tool_accuracy"], j.confidence) == ("coding", "search_code", 1.0, 0.6)
    assert j.cost_usd == pytest.approx(2 * 0.000006) and j.latency_ms == 140.0      # sequential: the sum


def test_baselines_are_parsed_and_scored(offline):
    r = exp.run_experiment(exp.EXAMPLES["'Refund' in a code question"])
    assert r.runs["llm_agent_router"].raw["tool"] == "search_code"
    flat = r.runs["flat_agent"]
    assert (flat.label, flat.raw["tool"], flat.raw["tool_accuracy"]) == ("finance", "issue_refund", 0.0)


def test_keywords_are_not_enough():
    """A keyword router (the word 'refund' means finance, 'order' means support...) gets many rows wrong."""
    words = {"finance": r"refund|invoice|revenue|charge|billed", "support": r"order|password|account|parcel",
             "coding": r"code|test|branch|pr\b|import|endpoint", "research": r"paper|arxiv|http|latest"}
    wrong = sum(next((a for a, w in words.items() if re.search(w, r["text"], re.I)), None) != r["label"]
                for r in exp.DATASET)
    assert wrong >= 6
