"""Project 15, offline: the static checks' blind spots, per-rule precision/recall, one call with four rules,
gold never reaching a model, and that the dataset needs more than patterns."""

import importlib

import pytest

exp = importlib.import_module("projects.15_semantic_linter.experiment")
rules = importlib.import_module("projects.15_semantic_linter.rules")
openrouter = importlib.import_module("shared.openrouter")


def test_static_checks_see_patterns_not_meaning():
    ex = exp.EXAMPLES
    assert rules.static_checks(ex["Debug flag skips auth"]["path"], ex["Debug flag skips auth"]["code"]) == []   # missed
    assert rules.static_checks(ex["Masked token, looks bad"]["path"], ex["Masked token, looks bad"]["code"]) == ["sensitive_exposure"]
    assert rules.static_checks("repositories/orders.py", "db.session.query(Order)") == []     # layering is path-aware
    assert rules.static_checks("routes/orders.py", "db.session.query(Order)") == ["layering"]


@pytest.mark.parametrize("flagged, gold, want", [
    (["a"], ["a"], (1.0, 1.0)), (["a", "b"], ["a"], (0.5, 1.0)), ([], ["a"], (None, 0.0)),
    (["a"], [], (0.0, None)), ([], [], (None, None)),
])
def test_precision_recall(flagged, gold, want):
    assert rules.precision_recall(flagged, gold) == want


def test_one_call_four_rules_and_gold_stays_out(monkeypatch):
    seen = []

    def decide(state, q):
        seen.append((state, q))
        p = {"auth_bypass": 0.9, "layering": 0.2, "sensitive_exposure": 0.7, "hardcoded_secret": 0.05}
        return {"id": "d", "model": "typesafe/jev-1.13-20260917", "answers": {k: {"noul": p[k]} for k in q},
                "usage": {"input_tokens": 400, "output_tokens": 0, "cost": 0.00001}}, 100.0
    monkeypatch.setattr(openrouter, "decide", decide)

    class Fake:
        def with_structured_output(self, *a, **k):
            return self
    monkeypatch.setattr(exp, "chat_model", lambda *a: Fake())
    monkeypatch.setattr(exp, "metered_call", lambda n, llm, m: ({"parsed": {"violations": ["layering", "zzz"]}},
                        {"model": "m", "latency_ms": 900.0, "input_tokens": 300, "output_tokens": 9, "cost_usd": 0.00004}))
    r = exp.run_experiment(exp.EXAMPLES["Query in a route"])
    (state, q), = seen
    assert set(state) == {"path", "code"} and set(q) == set(rules.RULES)
    j = r.runs["jev"]
    assert j.label == "flag" and j.raw["violations"] == ["auth_bypass", "sensitive_exposure"]
    assert j.raw["p_of"] == "worst rule" and j.probability == max(j.raw["rules"].values())   # the bar's label (re-test)
    assert (j.raw["rule_precision"], j.raw["rule_recall"]) == (0.5, 0.5)      # gold: layering + sensitive_exposure
    assert r.runs["static_checks"].cost_usd == 0.0
    assert r.runs["llm_reviewer"].raw["violations"] == ["layering"]            # unknown rule id dropped


def test_the_dataset_needs_more_than_patterns():
    got = [("flag" if rules.static_checks(r["input"]["path"], r["input"]["code"]) else "clean", r["label"]) for r in exp.DATASET]
    assert sum(g == e for g, e in got) / len(got) <= 0.7
    assert sum(g == "clean" and e == "flag" for g, e in got) >= 3 and sum(g == "flag" and e == "clean" for g, e in got) >= 3
    assert all(set(r["input"]["gold"]) <= set(rules.RULES) for r in exp.DATASET)
