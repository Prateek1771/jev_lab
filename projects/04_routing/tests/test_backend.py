"""Project 04, offline: the policy table, the reference's two band bugs, and the structural invariant."""

import importlib
import random

import pytest

from core.run import Run

exp = importlib.import_module("projects.04_routing.experiment")
jev_client = importlib.import_module("projects.04_routing.jev_client")
policy = importlib.import_module("projects.04_routing.policy")

OK = {"has_order": True, "prior_refunds_30d": 0, "within_return_window": True}


@pytest.mark.parametrize("intent,conf,policy_ok,churn,facts,expected", [
    ("refund", 0.95, 0.95, 0.2, OK, "refund_auto"),
    ("refund", 0.95, 0.95, 0.2, OK | {"has_order": False}, "refund_confirm"),
    ("refund", 0.95, 0.95, 0.2, OK | {"prior_refunds_30d": 2}, "refund_confirm"),   # the limit is < 2
    ("refund", 0.95, 0.95, 0.2, OK | {"prior_refunds_30d": 1}, "refund_auto"),
    ("refund", 0.95, 0.60, 0.2, OK, "refund_confirm"),                               # supported, not enough to pay alone
    ("refund", 0.95, 0.10, 0.2, OK, "block"),                                        # the policy says no
    ("refund", 0.60, 0.95, 0.2, OK, "refund_confirm"),                               # intent only fairly sure
    ("status", 0.95, 0.10, 0.2, OK, "route_queue"),
    ("refund", 0.30, 0.95, 0.2, OK, "human"),
])
def test_policy_table(intent, conf, policy_ok, churn, facts, expected):
    assert policy.choose(intent, conf, policy_ok, churn, facts)[0] == expected


def test_reference_bug_1_churn_cannot_leave_an_auto_refund_behind():
    """customer_support.py:153 appends start_refund_flow:auto; lines 166-169 then downgrade the band to
    CONFIRM for high churn but keep the action. Here high churn is decided BEFORE any action exists."""
    decision, reason = policy.choose("refund", 0.95, 0.95, 1.8, OK)
    assert decision == "refund_confirm" and "churn" in reason


def test_reference_bug_2_low_intent_confidence_is_never_overwritten():
    """In the reference, band starts HUMAN when intent confidence is low, the refund branch then
    reassigns band = AUTO, and the last check only re-tests department confidence. Here rules return."""
    assert policy.choose("refund", 0.30, 0.99, 0.0, OK)[0] == "human"


@pytest.mark.parametrize("days,inside", [(30, True), (31, False), (0, True), (None, False)])
def test_return_window_is_computed_in_code(days, inside):
    facts = exp.facts_from({"message": "x", "order": "o", "prior_refunds_30d": "3", "days_since_delivery": days})
    assert facts["within_return_window"] is inside and facts["prior_refunds_30d"] == 3


def fake_answers(rnd):
    # values on both sides of every threshold, so all five edges get exercised (uniform noise almost never
    # satisfies all six auto-refund conditions at once)
    return {"intent": rnd.choice(["refund", "refund", "status", "bug", "other"]),
            "intent_conf": rnd.choice([0.30, 0.60, 0.95]), "policy_ok": rnd.choice([0.10, 0.60, 0.95]),
            "churn": rnd.choice([0.2, 1.8]), "model": "typesafe/jev-1.13-20260917", "latency_ms": 100.0,
            "input_tokens": 200, "output_tokens": 30, "cost_usd": 0.000009, "id": "gen-dec-4"}


def test_the_graph_can_only_auto_refund_on_the_auto_edge(monkeypatch):
    """300 random Jev answers and ticket facts through the REAL compiled graph: every run takes exactly
    one action edge, and start_refund_flow:auto appears only when the decision and band say auto."""
    rnd = random.Random(4)
    monkeypatch.setattr(jev_client, "ask_ticket", lambda state, intents: fake_answers(rnd))
    monkeypatch.setattr(exp, "baseline_node", lambda s: {})
    monkeypatch.setattr(exp, "structured_node", lambda s: {})
    graph = exp.build_graph()   # rebuilt so the patched nodes are the ones wired in
    seen = set()
    for _ in range(300):
        inp = {"message": "m", "order": rnd.choice(["o", None]), "prior_refunds_30d": rnd.randint(0, 3),
               "days_since_delivery": rnd.choice([None, 5, 40])}
        jev = graph.invoke({"input": inp})["jev"]
        seen.add(jev.label)
        auto_refund = "start_refund_flow:auto" in jev.raw["actions"]
        assert auto_refund == (jev.label == "refund_auto")
        assert not auto_refund or jev.raw["band"] == "auto"
        assert jev.raw["actions"]                            # some action node always ran
    assert seen == set(policy.DECISIONS)                     # and every edge was exercised


def test_run_experiment_offline(monkeypatch):
    monkeypatch.setattr(jev_client, "ask_ticket", lambda state, intents: fake_answers(random.Random(1)) | {
        "intent": "refund", "intent_conf": 0.93, "policy_ok": 0.95, "churn": 0.3})
    fake = lambda variant: (lambda system, user, labels: Run(variant, "m", "refund_auto", None, 300.0, 200, 3, 0.00004))
    monkeypatch.setattr(exp, "ask_plain", fake("baseline"))
    monkeypatch.setattr(exp, "ask_structured", fake("structured"))
    r = exp.run_experiment(exp.EXAMPLES["Duplicate charge"])
    assert [run.label for run in r.runs.values()] == ["refund_auto"] * 3
    assert r.runs["jev"].raw["actions"] == ["start_refund_flow:auto", "route:queue.billing"]


def test_baselines_get_the_same_facts_as_the_policy():
    view = exp.llm_view(exp.EXAMPLES["Outside return window"], exp.facts_from(exp.EXAMPLES["Outside return window"]))
    assert '"within_return_window": false' in view and '"prior_refunds_30d": 0' in view
