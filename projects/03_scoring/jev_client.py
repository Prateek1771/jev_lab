"""Jev side of project 03: one Score question (an ordered rubric) over OpenRouter's Decisions API."""

from config import settings
from core.run import Run
from shared.openrouter import decide


def ask_score(state, name: str, instructions: str, levels: dict[str, str]) -> Run:
    """levels: label -> rubric description, lowest first. Jev sees only the descriptions, in order."""
    labels, rubric = list(levels), list(levels.values())
    body, latency = decide(state, {name: {"type": "score", "instructions": instructions, "criteria": rubric}})
    ans = body["answers"][name]
    probs = {int(k): float(v) for k, v in ans["probabilities"].items()}   # JSON keys arrive as "0", "1", ...
    top = max(probs, key=probs.get)   # the level with the most probability, not round(score)
    usage = body.get("usage") or {}
    return Run(
        variant="jev",
        model=body.get("model", settings.JEV_MODEL),
        label=labels[top],
        confidence=float(ans["confidence"]),
        score=float(ans["score"]),        # expected position: sum(level * P(level))
        latency_ms=latency,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cost_usd=usage.get("cost"),
        raw={"probabilities": {labels[k]: p for k, p in sorted(probs.items())}, "levels": len(labels),
             "id": body.get("id")},
    )
