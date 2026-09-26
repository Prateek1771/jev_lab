"""Project 02 backend, offline: yes/no parsing, the threshold, and the full graph with fake network calls."""

import importlib

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from core.run import Run

exp = importlib.import_module("projects.02_detection.experiment")
jev_client = importlib.import_module("projects.02_detection.jev_client")
openrouter = importlib.import_module("shared.openrouter")
baseline = importlib.import_module("projects.02_detection.baseline")


def noul_body(p, cost=0.000004):
    # shape from OpenRouter's documented live response: {"type": "noul", "noul": 0.96}, no confidence
    usage = {"input_tokens": 90, "output_tokens": 10} | ({"cost": cost} if cost is not None else {})
    return {"id": "gen-dec-2", "model": "typesafe/jev-1.13-20260917",
            "answers": {"urgent": {"type": "noul", "noul": p}}, "usage": usage}


def fake_llm(text):
    return GenericFakeChatModel(messages=iter([AIMessage(
        content=text, response_metadata={"model_name": "google/gemini-3.1-flash-lite", "cost": 0.00002},
        usage_metadata={"input_tokens": 80, "output_tokens": 1, "total_tokens": 81},
    )]))


@pytest.mark.parametrize("text,expected", [
    ("yes", True),
    ("No.", False),
    ("Yes, it is time-sensitive.", True),
    ("NO", False),
    ("not really", None),        # "not" is not "no": refuse to guess
    ("yes and no", None),        # both: refuse to guess
    ("I know", None),            # "know" contains "no" as letters, not as a word
    ("", None),
])
def test_parse_yes_no(text, expected):
    assert baseline.parse_yes_no(text) == expected


@pytest.mark.parametrize("p,label", [(0.96, "urgent"), (0.5, "urgent"), (0.4999, "not_urgent"), (0.02, "not_urgent")])
def test_threshold_is_applied_in_code(monkeypatch, p, label):
    monkeypatch.setattr(openrouter, "decide", lambda state, q: (noul_body(p), 120.0))
    run = jev_client.ask_noul({"message": "x"}, "urgent", "s", {}, 0.5, "urgent", "not_urgent")
    assert run.label == label
    assert run.probability == p and run.confidence is None   # Noul has no confidence; don't invent one


def fake_structured(label="urgent"):
    return lambda system, user, labels: Run("structured", "google/gemini-3.1-flash-lite", label, None, 300.0, 95, 6, 0.00004)


def test_run_experiment_offline(monkeypatch):
    monkeypatch.setattr(openrouter, "decide", lambda state, q: (noul_body(0.91), 120.0))
    monkeypatch.setattr(baseline, "chat_model", lambda: fake_llm("Yes"))
    monkeypatch.setattr(exp, "ask_structured", fake_structured())
    r = exp.run_experiment("Production is down right now.")
    assert [run.label for run in r.runs.values()] == ["urgent", "urgent", "urgent"]
    assert r.runs["jev"].cost_usd == 0.000004 and r.runs["baseline"].cost_usd == 0.00002


def test_structured_prompt_answers_in_labels_not_yes_no():
    # the plain prompt asks for yes/no; the enforced schema only allows labels, so its prompt must say so
    assert "yes or no" in exp._BASELINE_SYSTEM and "yes or no" not in exp._STRUCTURED_SYSTEM
    assert all(label in exp._STRUCTURED_SYSTEM for label in exp.LABELS)


def test_noul_question_sent_as_declared(monkeypatch):
    sent = {}

    def capture(state, questions):
        sent.update(questions)
        return noul_body(0.1), 100.0

    monkeypatch.setattr(openrouter, "decide", capture)
    monkeypatch.setattr(baseline, "chat_model", lambda: fake_llm("no"))
    monkeypatch.setattr(exp, "ask_structured", fake_structured("not_urgent"))
    exp.run_experiment("x")
    assert sent["urgent"]["type"] == "noul"
    assert set(sent["urgent"]["criteria"]) == {"true", "false"}
