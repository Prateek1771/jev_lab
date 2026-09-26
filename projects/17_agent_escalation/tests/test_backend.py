"""Project 17, offline: the bands (auto / review / human), the reviewer only in the middle band, an unreadable
review never approves, the policy reaches Jev, and the human/review rates."""

import importlib

import pytest

exp = importlib.import_module("projects.17_agent_escalation.experiment")
openrouter = importlib.import_module("shared.openrouter")


class FakeLLM:
    def with_structured_output(self, *a, **k):
        return self


def call(cost):
    return {"model": "m", "latency_ms": 500.0, "input_tokens": 300, "output_tokens": 10, "cost_usd": cost}


@pytest.fixture
def offline(monkeypatch):
    rec = {"jev": [], "reviews": 0, "jev_conf": 0.95, "jev_choice": "approve", "self": (0.99, "approve"),
           "review": "reject"}

    def decide(state, q):
        rec["jev"].append(state)
        return {"id": "d", "model": "typesafe/jev-1.13-20260917",
                "answers": {"verdict": {"choice": rec["jev_choice"], "confidence": rec["jev_conf"], "probabilities": {}}},
                "usage": {"input_tokens": 250, "output_tokens": 0, "cost": 0.00001}}, 80.0
    monkeypatch.setattr(openrouter, "decide", decide)

    def metered(name, llm, msgs):
        if name == "review.frontier":
            rec["reviews"] += 1
            return {"parsed": {"verdict": rec["review"]}}, call(0.001)
        conf, verdict = rec["self"]
        return {"parsed": {"verdict": verdict, "confidence": conf}}, call(0.00003)
    monkeypatch.setattr(exp, "chat_model", lambda *a: FakeLLM())
    monkeypatch.setattr(exp, "metered_call", metered)
    return rec


@pytest.mark.parametrize("conf, choice, route, label", [
    (0.95, "approve", "auto", "execute"), (0.95, "reject", "auto", "reject"),
    (0.75, "approve", "review", "reject"),      # the reviewer (fake: reject) decides in the middle band
    (0.59, "approve", "human", None), (0.9, "approve", "auto", "execute"), (0.6, "approve", "review", "reject"),
])
def test_bands(offline, conf, choice, route, label):
    offline.update(jev_conf=conf, jev_choice=choice)
    j = exp.run_experiment(exp.EXAMPLES["Clear refund"]).runs["jev"]
    assert (j.raw["route"], j.label) == (route, label)
    assert j.raw["human"] == float(route == "human") and j.raw["reviewed"] == float(route == "review")


def test_policy_in_state_and_reviewer_cost_counted(offline):
    offline.update(jev_conf=0.7)
    r = exp.run_experiment(exp.EXAMPLES["Close call"])
    assert offline["jev"][0]["policy"] == exp.POLICY and set(offline["jev"][0]) == {"policy", "case", "proposed"}
    assert r.runs["jev"].cost_usd == pytest.approx(0.00001 + 0.001)
    assert r.runs["always_review"].raw["route"] == "review" and r.runs["always_review"].model == "m"
    assert offline["reviews"] == 2                      # Jev's middle band + always_review; self-confidence was 0.99


def test_overconfident_self_report_skips_review(offline):
    offline.update(self=(0.99, "approve"))              # the LLM is always sure
    run = exp.run_experiment(exp.EXAMPLES["Refund to a different card"]).runs["llm_self_confidence"]
    assert run.raw["route"] == "auto" and run.label == "execute"


def test_unreadable_review_never_approves(offline, monkeypatch):
    monkeypatch.setattr(exp, "metered_call", lambda n, llm, m: ({"parsed": None}, call(0.001)))
    assert exp.review(exp.EXAMPLES["Clear refund"])[0] == "reject"


def test_dataset_balance():
    labels = [r["label"] for r in exp.DATASET]
    assert labels.count("execute") == labels.count("reject") == 10
