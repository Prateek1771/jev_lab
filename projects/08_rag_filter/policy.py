"""Which chunks the answer may use. Pure: Jev's per-chunk judgments in, kept ids out."""

from shared.metrics import precision_recall  # noqa: F401  (moved to shared/ in Phase 21: third copy)

INJECTION = 0.70    # the reference's noul_yes: an instruction aimed at an AI is dropped, however "useful"
SENSITIVE = 0.85    # the reference's high_stakes_noul: secrets or personal data are never passed on
USEFUL = 0.50       # P(chunk helps answer the question); a starting value, tune it on labeled rows


def verdict(j: dict) -> tuple[bool, str]:
    """Safety first, and the first match RETURNS: a chunk that is both useful and an injection is dropped."""
    if j["injection"] >= INJECTION:
        return False, f"injection (P {j['injection']:.2f})"
    if j["sensitive"] >= SENSITIVE:
        return False, f"sensitive data (P {j['sensitive']:.2f})"
    if j["useful"] >= USEFUL:
        return True, f"useful (P {j['useful']:.2f})"
    return False, f"not useful (P {j['useful']:.2f})"


def keep(judgments: list[dict], max_keep: int) -> list[str]:
    """Ids of the chunks that pass, most useful first, at most max_keep."""
    passed = [j for j in judgments if verdict(j)[0]]
    return [j["id"] for j in sorted(passed, key=lambda j: (-j["useful"], j["id"]))[:max_keep]]
