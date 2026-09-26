"""Jev side of project 05: two routing questions in ONE call. The grader lives in shared/grader.py."""

from shared.openrouter import decide_traced


def ask_route(task: str) -> dict:
    """Two separate judgments, not one "which model?" question: the reference's combined `model` Choice
    folds difficulty, capability and price into one answer, which its own README says not to do."""
    a, meta = decide_traced("jev.route", {"task": task}, {
        "difficulty": {"type": "score", "instructions": "How hard is this task for a language model to do well?",
                       "criteria": ["Easy: lookup, rewrite, or one-step answer",
                                    "Moderate: several steps or some domain knowledge",
                                    "Hard: deep reasoning, expert knowledge, or subtle trade-offs"]},
        "high_risk": {"type": "noul",
                      "instructions": "A wrong or incomplete answer to this task could cause real harm",
                      "criteria": {"true": "Money, security, law, health, or data loss depends on getting it right",
                                   "false": "A mistake would be cheap and easy to notice"}},
    })
    return {"difficulty": float(a["difficulty"]["score"]),
            "difficulty_conf": float(a["difficulty"]["confidence"]),   # the confidence of the question we route on
            "high_risk": float(a["high_risk"]["noul"])} | meta

