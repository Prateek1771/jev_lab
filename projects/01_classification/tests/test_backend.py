"""Project 01 backend, offline: parsing, cost, and the full graph with fake network calls.
The shared plumbing (decide, chat_model, ask_structured) is tested in tests/test_shared.py."""

import importlib
import time

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from core.run import Run
from shared.parse import parse_label

exp = importlib.import_module("projects.01_classification.experiment")
jev_client = importlib.import_module("projects.01_classification.jev_client")
openrouter = importlib.import_module("shared.openrouter")

ALLOWED = set(exp.CRITERIA)

JEV_BODY = {  # shape copied from OpenRouter's documented live Decisions response
    "id": "gen-dec-1", "model": "typesafe/jev-1.13-20260917", "provider": "TypeSafe",
    "answers": {"team": {"type": "choice", "choice": "billing", "confidence": 0.91,
                         "probabilities": {"billing": 0.91, "technical": 0.09}}},
    "usage": {"input_tokens": 120, "output_tokens": 30, "cost": 0.00000504},
}


def fake_llm(text="Billing.", cost=0.00003):
    meta = {"model_name": "google/gemini-3.1-flash-lite"} | ({"cost": cost} if cost is not None else {})
    return GenericFakeChatModel(messages=iter([AIMessage(
        content=text, response_metadata=meta,
        usage_metadata={"input_tokens": 90, "output_tokens": 2, "total_tokens": 92},
    )]))


def fake_structured(label="billing"):
    return lambda system, user, labels: Run("structured", "google/gemini-3.1-flash-lite", label, None, 300.0, 95, 6, 0.00004)


@pytest.mark.parametrize("text,expected", [
    ("billing", "billing"),
    ("Billing.", "billing"),
    ("`technical`", "technical"),
    ("  SALES\n", "sales"),
    ("Label: account", "account"),
    ("I think this is billing but could be technical", None),   # two labels: refuse to guess
    ("finance", None),                                          # invented label
    ("", None),
])
def test_parse_label(text, expected):
    assert parse_label(text, ALLOWED) == expected


def test_run_experiment_offline(monkeypatch):
    monkeypatch.setattr(jev_client, "decide", lambda state, q: (JEV_BODY, 150.0))
    monkeypatch.setattr(openrouter, "chat_model", lambda: fake_llm())
    monkeypatch.setattr(exp, "ask_structured", fake_structured())

    r = exp.run_experiment("charged twice")

    assert list(r.runs) == ["jev", "baseline", "structured"]      # display order = NODES order
    assert {v: run.label for v, run in r.runs.items()} == {"jev": "billing", "baseline": "billing", "structured": "billing"}
    assert r.runs["jev"].model == "typesafe/jev-1.13-20260917"   # the snapshot that answered, not what we asked for
    assert r.runs["jev"].cost_usd == 0.00000504                   # reported by OpenRouter, not computed
    assert r.runs["baseline"].cost_usd == 0.00003


def test_branches_run_in_parallel(monkeypatch):
    def slow(result):
        def f(*a, **k):
            time.sleep(0.5)
            return result() if callable(result) else result
        return f

    monkeypatch.setattr(jev_client, "decide", slow((JEV_BODY, 500.0)))
    monkeypatch.setattr(exp, "ask_structured", slow(lambda: fake_structured()(None, None, None)))

    class SlowLLM:
        def invoke(self, messages, config=None):
            time.sleep(0.5)
            return fake_llm().invoke(messages)

    monkeypatch.setattr(openrouter, "chat_model", lambda: SlowLLM())
    t0 = time.perf_counter()
    exp.run_experiment("x")
    assert time.perf_counter() - t0 < 1.3   # serial would be >= 1.5 s


def test_missing_cost_is_none_not_zero(monkeypatch):
    monkeypatch.setattr(openrouter, "chat_model", lambda: fake_llm(cost=None))
    run = openrouter.ask_plain("sys", "ticket", ALLOWED)
    assert run.cost_usd is None
