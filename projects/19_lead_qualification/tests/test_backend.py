"""Project 19, offline: the routing code (size checked in code), points scoring's blind spots, one call with two
Scores, and that the dataset needs more than points."""

import importlib

import pytest

from core.run import Run

exp = importlib.import_module("projects.19_lead_qualification.experiment")
scoring = importlib.import_module("projects.19_lead_qualification.scoring")
openrouter = importlib.import_module("shared.openrouter")


@pytest.mark.parametrize("fit, intent, employees, want", [
    (1.9, 1.9, 200, "sales_now"), (1.9, 1.9, 45, "nurture"), (1.9, 1.9, 3, "disqualify"),
    (1.9, 0.4, 400, "nurture"), (0.3, 1.9, 400, "disqualify"), (1.2, 1.9, 400, "nurture"), (1.9, 1.9, 2500, "nurture"),
])
def test_route_is_code(fit, intent, employees, want):
    assert scoring.route(fit, intent, employees) == want


def test_points_read_words():
    ex = exp.EXAMPLES
    assert scoring.points(ex["Big title, tiny company"])[0] == "nurture"       # 3 employees still gets 55 points
    assert scoring.points(ex["Buying for the boss"])[0] == "nurture"           # no leader title, no 'demo'
    assert scoring.points(ex["Right fit, just reading"])[0] == "nurture"


def test_one_call_two_scores(monkeypatch):
    seen = []

    def decide(state, q):
        seen.append((state, q))
        return {"id": "d", "model": "typesafe/jev-1.13-20260917", "answers": {
            "icp_fit": {"score": 1.8, "confidence": 0.9, "probabilities": {}},
            "purchase_intent": {"score": 1.7, "confidence": 0.7, "probabilities": {}}},
            "usage": {"input_tokens": 400, "output_tokens": 0, "cost": 0.00001}}, 90.0
    monkeypatch.setattr(openrouter, "decide", decide)
    monkeypatch.setattr(exp, "ask_structured", lambda s, u, labels: Run("structured", "m", "nurture", None, 900.0, 300, 5, 0.00004))
    r = exp.run_experiment(exp.EXAMPLES["Big title, tiny company"])
    (state, q), = seen
    assert set(q) == {"icp_fit", "purchase_intent"} and state["icp"] == scoring.JEV_ICP and "company_size" not in state["icp"]
    j = r.runs["jev"]
    assert (j.label, j.confidence) == ("disqualify", 0.7)        # strong scores, but 3 employees: code says no
    assert r.runs["points"].cost_usd == 0.0


def test_the_dataset_needs_more_than_points():
    got = [(scoring.points(r["input"])[0], r["label"]) for r in exp.DATASET]
    assert sum(g == e for g, e in got) / len(got) <= 0.7
