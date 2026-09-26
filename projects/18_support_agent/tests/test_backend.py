"""Project 18, offline: one triage call, escalation in code, the specialist only when routed, grading only when
there is an answer and a rubric, and the rubric never reaching triage or the agents."""

import importlib

import pytest

exp = importlib.import_module("projects.18_support_agent.experiment")
openrouter = importlib.import_module("shared.openrouter")


class FakeLLM:
    def with_structured_output(self, *a, **k):
        return self


def call():
    return {"model": "m", "latency_ms": 700.0, "input_tokens": 300, "output_tokens": 40, "cost_usd": 0.00004,
            "finish_reason": "stop"}


@pytest.fixture
def offline(monkeypatch):
    rec = {"triage": [], "llm": [], "intent": "billing", "human": 0.1, "single": ("billing", "an answer")}

    def decide(state, q):
        if "correct" in q:
            return {"answers": {"correct": {"noul": 0.9}}, "usage": {"cost": 0.00001}, "id": "g"}, 50.0
        rec["triage"].append((state, q))
        return {"id": "d", "model": "typesafe/jev-1.13-20260917", "answers": {
            "intent": {"choice": rec["intent"], "confidence": 0.9, "probabilities": {}},
            "needs_human": {"noul": rec["human"]}, "urgency": {"noul": 0.2}},
            "usage": {"input_tokens": 300, "output_tokens": 0, "cost": 0.00001}}, 90.0
    monkeypatch.setattr(openrouter, "decide", decide)

    def metered(name, llm, msgs):
        rec["llm"].append((name, str([m.content for m in msgs])))
        if name == "agent.single":
            route, answer = rec["single"]
            return {"parsed": {"route": route, "answer": answer}}, call()
        from langchain_core.messages import AIMessage
        return AIMessage("Your duplicate $49 charge will be refunded."), call()
    monkeypatch.setattr(exp, "chat_model", lambda *a: FakeLLM())
    monkeypatch.setattr(exp, "metered_call", metered)
    return rec


def test_one_triage_call_then_specialist_then_grade(offline):
    inp = exp.EXAMPLES["Angry, but routine"]
    r = exp.run_experiment(inp)
    (state, q), = offline["triage"]
    assert set(q) == {"intent", "needs_human", "urgency"} and set(state) == {"message", "facts"}
    j = r.runs["jev"]
    assert (j.label, j.quality) == ("billing", 0.9) and j.raw["answer"].startswith("Your duplicate")
    assert j.cost_usd == pytest.approx(0.00001 + 0.00004) and j.raw["grade_cost"] == 0.00001
    assert inp["rubric"] not in str(offline["llm"]) + str(offline["triage"])      # rubric only reaches the grader


def test_escalation_is_code_and_skips_the_specialist(offline):
    offline.update(human=0.8, single=("human", "ignored"))
    r = exp.run_experiment(exp.EXAMPLES["Calm, but legal"])
    j, s = r.runs["jev"], r.runs["single_agent"]
    assert (j.label, j.raw["answer"], j.quality) == ("human", None, None)
    assert [n for n, _ in offline["llm"]] == ["agent.single"]                     # no specialist call for Jev
    assert (s.label, s.raw["answer"], s.quality) == ("human", None, None)


def test_single_agent_outside_enum_is_invalid(offline):
    offline.update(single=("sales", "hi"))
    assert exp.run_experiment(exp.EXAMPLES["Where is my order"]).runs["single_agent"].label is None


def test_routed_rows_have_rubrics_and_human_rows_do_not():
    for r in exp.DATASET:
        assert ("rubric" in r["input"]) == (r["label"] != "human"), r["text"]
