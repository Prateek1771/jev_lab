"""Project 05, offline: the routing table, the reference's confidence mismatch, rubric isolation, and costs."""

import importlib

import pytest

from core.run import Run

exp = importlib.import_module("projects.05_model_router.experiment")
jev_client = importlib.import_module("projects.05_model_router.jev_client")
router = importlib.import_module("projects.05_model_router.router")
openrouter = importlib.import_module("shared.openrouter")
grader = importlib.import_module("shared.grader")


@pytest.mark.parametrize("difficulty,conf,risk,expected", [
    (0.1, 0.90, 0.10, "fast"),
    (1.0, 0.90, 0.10, "balanced"),
    (1.8, 0.90, 0.10, "frontier"),
    (0.1, 0.30, 0.10, "frontier"),    # unsure how hard it is: route up, never down
    (0.1, 0.90, 0.85, "frontier"),    # looks easy, high stakes
    (0.79, 0.90, 0.69, "fast"),       # just under every cut
    (0.8, 0.45, 0.70, "frontier"),    # exactly on the cuts
])
def test_router_table(difficulty, conf, risk, expected):
    assert router.tier_for(difficulty, conf, risk)[0] == expected


def test_unsure_is_checked_before_difficulty():
    tier, reason = router.tier_for(0.0, 0.2, 0.0)
    assert tier == "frontier" and "unsure" in reason


def decide_fake(calls, difficulty=0.2, conf=0.9, risk=0.1, quality=0.8):
    """Stands in for shared.openrouter.decide; records what Jev was shown."""
    def fake(state, questions):
        calls.append(state)
        usage = {"input_tokens": 100, "output_tokens": 0, "cost": 0.000004}
        if "correct" in questions:
            return {"answers": {"correct": {"noul": quality}}, "usage": usage, "id": "g"}, 50.0
        return {"answers": {"difficulty": {"score": difficulty, "confidence": conf},
                            "high_risk": {"noul": risk}},
                "model": "typesafe/jev-1.13-20260917", "usage": usage, "id": "r"}, 80.0
    return fake


def test_jev_run_uses_the_confidence_of_the_question_it_routed_on(monkeypatch):
    """The reference force-upgrades on high risk but keeps the confidence Jev gave the model it REJECTED.
    Here there is no model Choice: the confidence shown is the difficulty question's own."""
    monkeypatch.setattr(openrouter, "decide", decide_fake([], difficulty=0.1, conf=0.62, risk=0.9))
    a = jev_client.ask_route("t")
    assert router.tier_for(a["difficulty"], a["difficulty_conf"], a["high_risk"])[0] == "frontier"
    assert a["difficulty_conf"] == 0.62


def test_grader_reads_p_true_as_quality(monkeypatch):
    monkeypatch.setattr(openrouter, "decide", decide_fake([], quality=0.31))
    assert grader.grade("t", "r", "a")["quality"] == 0.31


class FakeChat:
    """Stands in for the tier models and the LLM router; records every message list it gets."""
    def __init__(self, calls, model):
        self.calls, self.model = calls, model

    def invoke(self, messages):
        self.calls.append((self.model, " ".join(m.content for m in messages)))
        return type("Msg", (), {"content": f"answer from {self.model}",
                                "usage_metadata": {"input_tokens": 40, "output_tokens": 200},
                                "response_metadata": {"model_name": self.model, "cost": 0.001,
                                                      "finish_reason": "stop"}})()


@pytest.fixture
def offline(monkeypatch):
    jev_calls, chat_calls = [], []
    monkeypatch.setattr(openrouter, "decide", decide_fake(jev_calls))
    monkeypatch.setattr(exp, "chat_model", lambda model=None, max_tokens=None, reasoning_effort=None: (
        chat_calls.append(("effort", f"{model}:{reasoning_effort}")) or FakeChat(chat_calls, model)))
    monkeypatch.setattr(exp, "ask_structured", lambda system, user, labels: (
        chat_calls.append(("router", system + user)) or Run("structured", "m", "balanced", None, 300.0, 90, 3, 0.00002)))
    return jev_calls, chat_calls


def test_run_experiment_offline(offline):
    r = exp.run_experiment(exp.EXAMPLES["Short but hard"])
    assert [run.label for run in r.runs.values()] == ["fast", "balanced", "frontier"]
    jev = r.runs["jev"]
    assert jev.model == "google/gemini-3.1-flash-lite" and jev.quality == 0.8
    assert jev.cost_usd == pytest.approx(0.000004 + 0.001)      # routing + answering ...
    assert jev.raw["grade_cost"] == 0.000004                     # ... grading is kept apart
    assert jev.latency_ms >= 80.0 and jev.input_tokens == 140
    assert r.runs["frontier"].cost_usd == pytest.approx(0.001)  # no routing call at all


def test_rubric_reaches_only_the_grader(offline):
    jev_calls, chat_calls = offline
    inp = exp.EXAMPLES["Looks easy, high stakes"]
    exp.run_experiment(inp)
    marker = "caveat"   # appears in the rubric, not in the task
    assert marker not in inp["task"] and marker in inp["rubric"]
    assert all(marker not in text for _, text in chat_calls)                 # no router, no answerer
    graded = [s for s in jev_calls if "rubric" in s]
    assert len(graded) == 3 and all("rubric" not in s for s in jev_calls if s not in graded)


def test_missing_cost_is_not_a_partial_sum():
    assert exp._total(0.001, None) is None and exp._total(0.001, 0.002) == pytest.approx(0.003)


def test_every_row_has_a_task_and_a_rubric():
    assert all(row["input"]["task"].strip() and row["input"]["rubric"].strip() for row in exp.DATASET)


def test_the_balanced_tier_answers_without_hidden_thinking(offline):
    """Real test: gemini-3.5-flash spent up to 765 of 800 tokens thinking and its answers were cut off.
    The balanced tier is called with reasoning effort 'minimal'; the other tiers with none."""
    _, chat_calls = offline
    exp.answer("balanced", "t")
    exp.answer("fast", "t")
    efforts = [text for kind, text in chat_calls if kind == "effort"]
    assert efforts[-2].endswith(":minimal") and efforts[-1].endswith(":None")
