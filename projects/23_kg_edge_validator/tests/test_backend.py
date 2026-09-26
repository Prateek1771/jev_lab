"""Project 23, offline: invented entities rejected in code, only "supports" stores, the edge's meaning is sent."""

import importlib

import pytest

from core.run import Run

exp = importlib.import_module("projects.23_kg_edge_validator.experiment")
openrouter = importlib.import_module("shared.openrouter")


def choice(c, conf=0.9, seen=None):
    def decide(state, q):
        if seen is not None:
            seen.append((state, q))
        return {"id": "d", "model": "typesafe/jev-1.13-20260917", "answers": {"support": {
            "choice": c, "confidence": conf, "probabilities": {c: conf, "not_stated": round(1 - conf, 2)} if c != "not_stated" else {c: conf}}},
                "usage": {"input_tokens": 200, "output_tokens": 0, "cost": 0.000008}}, 80.0
    return decide


@pytest.fixture(autouse=True)
def llm(monkeypatch):
    monkeypatch.setattr(exp, "ask_structured", lambda s, u, labels: Run("structured", "m", "valid", None, 800.0, 200, 5, 0.00003))


@pytest.mark.parametrize("c, conf, want", [("supports", 0.9, "valid"), ("supports", 0.4, "invalid"),
                                           ("contradicts", 0.9, "invalid"), ("not_stated", 0.8, "invalid")])
def test_only_supports_stores(monkeypatch, c, conf, want):
    seen = []
    monkeypatch.setattr(openrouter, "decide", choice(c, conf, seen))
    r = exp.run_experiment(exp.EXAMPLES["Former job"])
    (state, q), = seen
    assert state["edge"]["means"] == "Priya Nair currently works at Contoso" and set(q["support"]["criteria"]) == {
        "supports", "contradicts", "not_stated"}
    assert r.runs["jev"].label == want and r.runs["store_all"].label == "valid"
    assert r.runs["jev"].probability == (conf if c == "supports" else 0.0)
    assert r.runs["llm_self_check"].variant == "llm_self_check"


def test_invented_entity_is_rejected_before_any_call(monkeypatch):
    seen = []
    monkeypatch.setattr(openrouter, "decide", choice("supports", seen=seen))
    r = exp.run_experiment(exp.EXAMPLES["Invented entity"])
    assert seen == [] and r.runs["jev"].label == "invalid" and "Microsoft" in r.runs["jev"].raw["reason"]


def test_entity_check_matches_words_not_exact_spans():
    doc = {"document": "The Riverside plant was sold.", "subject": "Riverside plant", "object": "Stark"}
    assert exp.missing_entities(doc) == ["Stark"]
    assert exp.missing_entities({**doc, "subject": "Northwind", "object": "plant Riverside"}) == ["Northwind"]


def test_every_relation_in_the_dataset_has_a_meaning():
    assert {r["input"]["relation"] for r in exp.DATASET} <= set(exp.RELATIONS)


def test_storing_everything_keeps_bad_edges():
    assert sum(r["label"] == "invalid" for r in exp.DATASET) >= 10
