"""Project 20, offline: facts computed in code, the bands, the ladder calling the frontier only above low,
and that the dataset needs more than rules."""

import importlib

import pytest

exp = importlib.import_module("projects.20_fraud_prescreen.experiment")
features = importlib.import_module("projects.20_fraud_prescreen.features")
openrouter = importlib.import_module("shared.openrouter")


def test_facts_are_code():
    f = features.features(exp.EXAMPLES["Big but normal"])
    assert f["amount_vs_usual"] == 13.3 and not f["new_device"] and not f["foreign"]


@pytest.mark.parametrize("score, band", [(0.2, "allow"), (0.93, "allow"), (0.94, "review"), (1.59, "review"), (1.6, "investigate")])
def test_bands(score, band):
    assert exp._band(score) == band


class FakeLLM:
    def with_structured_output(self, *a, **k):
        return self


@pytest.fixture
def offline(monkeypatch):
    rec = {"risk": 0.2, "frontier_calls": 0, "states": []}

    def decide(state, q):
        rec["states"].append(state)
        return {"id": "d", "model": "typesafe/jev-1.13-20260917",
                "answers": {"risk": {"score": rec["risk"], "confidence": 0.8, "probabilities": {}}},
                "usage": {"input_tokens": 250, "output_tokens": 0, "cost": 0.00001}}, 80.0
    monkeypatch.setattr(openrouter, "decide", decide)

    def metered(name, llm, msgs):
        rec["frontier_calls"] += 1
        return {"parsed": {"decision": "investigate"}}, {"model": "frontier", "latency_ms": 2500.0,
                                                         "input_tokens": 400, "output_tokens": 10, "cost_usd": 0.0012}
    monkeypatch.setattr(exp, "chat_model", lambda *a: FakeLLM())
    monkeypatch.setattr(exp, "metered_call", metered)
    return rec


def test_ladder_skips_the_frontier_when_jev_says_low(offline):
    r = exp.run_experiment(exp.EXAMPLES["Big but normal"])
    assert offline["frontier_calls"] == 1                         # frontier_all only
    lad = r.runs["ladder"]
    assert (lad.label, lad.raw["frontier"], lad.cost_usd) == ("allow", 0.0, 0.00001)
    assert set(offline["states"][0]) == {"transaction", "facts"} and offline["states"][0]["facts"]["amount_vs_usual"] == 13.3


def test_ladder_escalates_above_low(offline):
    offline["risk"] = 1.2
    r = exp.run_experiment(exp.EXAMPLES["Takeover pattern"])
    lad, jev = r.runs["ladder"], r.runs["jev"]
    assert (jev.label, lad.label, lad.raw["frontier"]) == ("review", "investigate", 1.0)
    assert lad.cost_usd == pytest.approx(0.00001 + 0.0012) and offline["frontier_calls"] == 2
    assert r.runs["rules_engine"].cost_usd == 0.0


def test_the_dataset_needs_more_than_rules():
    got = [(features.rules(r["input"])[0], r["label"]) for r in exp.DATASET]
    assert sum(g == e for g, e in got) / len(got) <= 0.7
