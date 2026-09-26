"""Project 03 backend, offline: Score parsing, argmax vs. average, and the full graph with fake network calls."""

import importlib

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from core.run import Run
from shared.parse import parse_label

exp = importlib.import_module("projects.03_scoring.experiment")
jev_client = importlib.import_module("projects.03_scoring.jev_client")
openrouter = importlib.import_module("shared.openrouter")


def score_body(probs: dict[int, float], confidence=0.9, cost=0.000006):
    # shape from OpenRouter's documented live response: score, confidence, probabilities, legend; keys are strings
    return {"id": "gen-dec-3", "model": "typesafe/jev-1.13-20260917",
            "answers": {"severity": {"type": "score", "score": sum(k * p for k, p in probs.items()),
                                     "confidence": confidence,
                                     "probabilities": {str(k): p for k, p in probs.items()},
                                     "legend": {str(i): d for i, d in enumerate(exp.LEVELS.values())}}},
            "usage": {"input_tokens": 150, "output_tokens": 40, "cost": cost}}


def fake_llm(text):
    return GenericFakeChatModel(messages=iter([AIMessage(
        content=text, response_metadata={"model_name": "google/gemini-3.1-flash-lite", "cost": 0.00002},
        usage_metadata={"input_tokens": 110, "output_tokens": 1, "total_tokens": 111},
    )]))


def ask():
    return jev_client.ask_score({"ticket": "x"}, "severity", exp.QUESTION, exp.LEVELS)


def test_rubric_is_sent_in_order(monkeypatch):
    sent = {}

    def capture(state, questions):
        sent.update(questions)
        return score_body({0: 0.1, 1: 0.2, 2: 0.7}), 100.0

    monkeypatch.setattr(jev_client, "decide", capture)
    ask()
    assert sent["severity"]["type"] == "score"
    assert sent["severity"]["criteria"] == list(exp.LEVELS.values())   # position IS the scale


def test_label_is_argmax_not_rounded_average(monkeypatch):
    """A split verdict: 40% low, 15% medium, 45% high. The average is 1.05 and rounds to 'medium',
    a level the model gave only 15%. The label is the level with the most probability."""
    monkeypatch.setattr(jev_client, "decide", lambda s, q: (score_body({0: 0.40, 1: 0.15, 2: 0.45}), 100.0))
    run = ask()
    assert run.score == pytest.approx(1.05)
    assert run.label == "high"
    assert run.raw["probabilities"] == {"low": 0.40, "medium": 0.15, "high": 0.45}


def test_confident_middle(monkeypatch):
    monkeypatch.setattr(jev_client, "decide", lambda s, q: (score_body({0: 0.05, 1: 0.9, 2: 0.05}, 0.85), 100.0))
    run = ask()
    assert (run.label, run.confidence) == ("medium", 0.85) and run.score == pytest.approx(1.0)


@pytest.mark.parametrize("text,expected", [("high", "high"), ("Medium.", "medium"), ("low or medium", None), ("", None)])
def test_parse_label(text, expected):
    assert parse_label(text, set(exp.LABELS)) == expected


def test_run_experiment_offline(monkeypatch):
    monkeypatch.setattr(jev_client, "decide", lambda s, q: (score_body({0: 0.02, 1: 0.08, 2: 0.9}), 110.0))
    monkeypatch.setattr(openrouter, "chat_model", lambda: fake_llm("high"))
    monkeypatch.setattr(exp, "ask_structured",
                        lambda system, user, labels: Run("structured", "m", "high", None, 300.0, 120, 6, 0.00004))
    r = exp.run_experiment("Checkout is down for all our customers.")
    assert [run.label for run in r.runs.values()] == ["high", "high", "high"]
    assert r.runs["jev"].score == pytest.approx(1.88) and r.runs["jev"].cost_usd == 0.000006
