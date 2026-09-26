"""Which model tier answers a task. Pure: Jev's two answers in, one tier out. No I/O, no model calls."""

# Starting values are the reference's (jev_usecases/model_routing.py). Tune them on labeled rows.
UNSURE = 0.45        # Jev's confidence in its own difficulty answer below this: don't gamble, use frontier
HIGH_RISK = 0.70     # P(a wrong answer causes real harm) at or above this: frontier, however easy it looks
FRONTIER_AT = 1.6    # difficulty score on 0..2 (easy, moderate, hard)
BALANCED_AT = 0.8    # ours; the reference has no middle cut because its middle tier comes from a Choice

TIERS = ["fast", "balanced", "frontier"]   # cheapest first


def tier_for(difficulty: float, difficulty_conf: float, high_risk: float) -> tuple[str, str]:
    """Most cautious rule first, and the first match RETURNS. Every doubt routes UP: a wasted frontier
    call costs cents, a wrong cheap answer costs whatever the answer was for."""
    if difficulty_conf < UNSURE:
        return "frontier", f"unsure how hard this is (confidence {difficulty_conf:.2f} < {UNSURE})"
    if high_risk >= HIGH_RISK:
        return "frontier", f"high stakes (P={high_risk:.2f} >= {HIGH_RISK})"
    if difficulty >= FRONTIER_AT:
        return "frontier", f"hard (difficulty {difficulty:.2f} >= {FRONTIER_AT})"
    if difficulty >= BALANCED_AT:
        return "balanced", f"moderate (difficulty {difficulty:.2f} >= {BALANCED_AT})"
    return "fast", f"easy (difficulty {difficulty:.2f} < {BALANCED_AT})"
