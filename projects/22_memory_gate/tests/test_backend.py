"""Project 22, offline: the store rule, secrets refused in code before any call, one call with four Nouls."""

import importlib

import pytest

from core.run import Run

exp = importlib.import_module("projects.22_memory_gate.experiment")
openrouter = importlib.import_module("shared.openrouter")


def nouls(p, seen=None):
    def decide(state, q):
        if seen is not None:
            seen.append((state, q))
        return {"id": "d", "model": "typesafe/jev-1.13-20260917", "answers": {k: {"noul": p.get(k, 0.1)} for k in q},
                "usage": {"input_tokens": 200, "output_tokens": 0, "cost": 0.000008}}, 80.0
    return decide


@pytest.fixture(autouse=True)
def llm(monkeypatch):
    monkeypatch.setattr(exp, "ask_structured", lambda s, u, labels: Run("structured", "m", "store", None, 800.0, 200, 5, 0.00003))


@pytest.mark.parametrize("p, want", [
    ({"durable": 0.9, "about_user": 0.9}, "store"),
    ({"durable": 0.9, "about_user": 0.9, "already_known": 0.8}, "skip"),
    ({"durable": 0.3, "about_user": 0.9}, "skip"),
    ({"durable": 0.9, "about_user": 0.2}, "skip"),
    ({"durable": 0.9, "about_user": 0.9, "secret": 0.7}, "skip"),
])
def test_store_rule(monkeypatch, p, want):
    seen = []
    monkeypatch.setattr(openrouter, "decide", nouls(p, seen))
    r = exp.run_experiment(exp.EXAMPLES["A lasting preference"])
    (state, q), = seen
    assert set(q) == {"durable", "about_user", "already_known", "secret"} and set(state) == {"message", "memories"}
    assert r.runs["jev"].label == want and r.runs["store_everything"].label == "store"


def test_secret_shapes_are_refused_before_any_call(monkeypatch):
    seen = []
    monkeypatch.setattr(openrouter, "decide", nouls({"durable": 0.9, "about_user": 0.9}, seen))
    r = exp.run_experiment({"message": "my password is sunflower42", "memories": []})
    assert seen == [] and r.runs["jev"].label == "skip" and r.runs["jev"].cost_usd == 0.0


def test_storing_everything_keeps_the_junk():
    assert sum(r["label"] == "skip" for r in exp.DATASET) >= 10
