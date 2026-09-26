"""Project 13, offline: one call with three flags, block on any, the policy reaches Jev, and the graph."""

import importlib

import pytest

from core.run import Run

exp = importlib.import_module("projects.13_output_safety_gate.experiment")
openrouter = importlib.import_module("shared.openrouter")


def fake_decide(flags, seen=None):
    def decide(state, questions):
        if seen is not None:
            seen.append((state, questions))
        return {"id": "d", "model": "typesafe/jev-1.13-20260917",
                "answers": {k: {"noul": flags.get(k, 0.05)} for k in questions},
                "usage": {"input_tokens": 300, "output_tokens": 0, "cost": 0.00001}}, 110.0
    return decide


@pytest.fixture(autouse=True)
def llm(monkeypatch):
    monkeypatch.setattr(exp, "ask_structured", lambda s, u, labels: Run("structured", "m", "release", None, 900.0, 300, 5, 0.00005))


@pytest.mark.parametrize("flags, label, reason", [
    ({}, "release", "no flag tripped: harmful 0.05, leaks_data 0.05, breaks_policy 0.05"),
    ({"leaks_data": 0.8}, "block", "tripped: leaks_data 0.80"),
    ({"harmful": 0.6, "breaks_policy": 0.9}, "block", "tripped: harmful 0.60, breaks_policy 0.90"),
    ({"breaks_policy": 0.4999}, "release", "no flag tripped: harmful 0.05, leaks_data 0.05, breaks_policy 0.50"),
])
def test_any_flag_blocks(monkeypatch, flags, label, reason):
    monkeypatch.setattr(openrouter, "decide", fake_decide(flags))
    run = exp.run_experiment(exp.EXAMPLES["Unauthorised promise"]).runs["jev"]
    assert (run.label, run.raw["reason"]) == (label, reason)
    assert run.probability == max([0.05, *flags.values()])       # what the sweep tunes
    assert run.raw["p_of"] == "worst flag"                        # the bar's label: not a yes/no (re-test)


def test_one_call_three_questions_policy_in_state(monkeypatch):
    seen = []
    monkeypatch.setattr(openrouter, "decide", fake_decide({}, seen))
    r = exp.run_experiment(exp.EXAMPLES["Another customer's address"])
    (state, questions), = seen
    assert set(questions) == {"harmful", "leaks_data", "breaks_policy"}
    assert state["policy"] == exp.POLICY and set(state) == {"policy", "user", "question", "reply"}
    assert list(r.runs) == ["jev", "no_gate", "llm_gate"] and r.runs["llm_gate"].variant == "llm_gate"
    assert r.runs["no_gate"].label == "release" and r.runs["no_gate"].cost_usd == 0.0


def test_without_a_gate_every_bad_reply_ships():
    bad = [r for r in exp.DATASET if r["label"] == "block"]
    assert len(bad) >= 10 and {r["input"]["user"] for r in exp.DATASET} == {exp.EXAMPLES["Unauthorised promise"]["user"]}


def test_gate_and_sweep_specs_match_labels():
    assert {exp.SAFETY["unsafe"], exp.SAFETY["safe"], exp.SWEEP["positive"]} <= set(exp.LABELS)
