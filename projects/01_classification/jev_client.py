"""Jev side of project 01: one Choice question over OpenRouter's Decisions API."""

from config import settings
from core.run import Run
from shared.openrouter import decide   # moved to shared/ in Phase 3: the third identical copy


def ask_choice(state, name: str, instructions: str, criteria: dict) -> Run:
    body, latency = decide(state, {name: {"type": "choice", "instructions": instructions, "criteria": criteria}})
    ans = body["answers"][name]
    usage = body.get("usage") or {}
    return Run(
        variant="jev",
        model=body.get("model", settings.JEV_MODEL),   # dated snapshot, e.g. typesafe/jev-1.13-20260917
        label=ans["choice"],
        confidence=ans["confidence"],
        latency_ms=latency,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),   # reported, but not billed
        cost_usd=usage.get("cost"),                    # optional in the schema: None, never 0
        raw={"probabilities": ans["probabilities"], "id": body.get("id")},
    )
