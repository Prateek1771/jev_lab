"""Project 12, offline: the detectors (Luhn, spans, redaction), the Noul state and threshold, redaction on the
Jev path, and that the dataset needs more than regexes."""

import importlib

import pytest

from core.run import Run

exp = importlib.import_module("projects.12_pii_detector.experiment")
detectors = importlib.import_module("projects.12_pii_detector.detectors")
openrouter = importlib.import_module("shared.openrouter")


def test_luhn():
    assert detectors.luhn("4539148803436467") and detectors.luhn("4242424242424242")
    assert not detectors.luhn("4539148803436468")


@pytest.mark.parametrize("text, kinds", [
    ("Mail priya.nair@gmail.com or call +44 7700 900123.", ["email", "phone"]),
    ("Card 4539 1488 0343 6467 exp 09/28", ["card"]),
    ("Card 4539 1488 0343 6468", []),                         # fails Luhn: not a card, and too long for a phone
    ("SSN 078-05-1121", ["ssn"]),
    ("key sk-live-9f8a7b6c5d4e3f2a1b0c9d8e", ["api_key"]),
    ("my password is sunflower42", ["password"]),
    ("reset your password from settings on 2026-04-01", []),
    ("priya dot nair at gmail dot com", []),                 # the blind spot a model has to cover
])
def test_find(text, kinds):
    assert [h["kind"] for h in detectors.find(text)] == kinds


def test_redact_keeps_surrounding_text():
    t = "Card 4539 1488 0343 6467 exp 09/28, mail a@b.co"
    assert detectors.redact(t, detectors.find(t)) == "Card [CARD] exp 09/28, mail [EMAIL]"


def noul(p):
    return lambda state, q: ({"id": "d", "model": "typesafe/jev-1.13-20260917", "answers": {"pii": {"noul": p}},
                              "usage": {"input_tokens": 90, "output_tokens": 0, "cost": 0.000004}}, 80.0)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(exp, "ask_structured", lambda s, u, labels: Run("structured", "m", "pii", None, 300.0, 90, 5, 0.00003))


def test_jev_redacts_regex_spans_and_flags_the_rest(monkeypatch, offline):
    monkeypatch.setattr(openrouter, "decide", noul(0.95))
    r = exp.run_experiment(exp.EXAMPLES["Email and phone"])
    assert r.runs["jev"].label == "pii" and "[EMAIL]" in r.runs["jev"].raw["redacted"]
    r = exp.run_experiment(exp.EXAMPLES["No regex can see it"])
    assert r.runs["jev"].label == "pii" and "by hand" in r.runs["jev"].raw["reason"]
    assert r.runs["regex"].label == "clean" and r.runs["regex"].cost_usd == 0.0


def test_jev_state_is_the_text_and_threshold_is_code(monkeypatch, offline):
    seen = []
    monkeypatch.setattr(openrouter, "decide", lambda s, q: (seen.append(s) or noul(0.4999)(s, q)))
    r = exp.run_experiment(exp.EXAMPLES["Looks like PII, isn't"])
    assert seen == [{"text": exp.EXAMPLES["Looks like PII, isn't"]}] and r.runs["jev"].label == "clean"
    assert "redacted" not in r.runs["jev"].raw        # clean text goes to the LLM untouched
    assert r.runs["regex"].label == "pii"             # a test card, a support address, an order number


def test_the_dataset_needs_more_than_regexes():
    got = [("pii" if detectors.find(r["text"]) else "clean", r["label"]) for r in exp.DATASET]
    missed = sum(g == "clean" and e == "pii" for g, e in got)
    flagged = sum(g == "pii" and e == "clean" for g, e in got)
    assert sum(g == e for g, e in got) / len(got) <= 0.7 and missed >= 3 and flagged >= 3


def test_gate_and_sweep_specs_match_labels():
    assert {exp.SAFETY["unsafe"], exp.SAFETY["safe"], exp.SWEEP["positive"]} <= set(exp.LABELS)
