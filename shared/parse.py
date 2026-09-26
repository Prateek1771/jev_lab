"""Free-text answer parsing, identical in three projects (01, 03, 04)."""


def parse_label(text: str, allowed: set[str]) -> str | None:
    """Map free text back into the schema. Returns None when it cannot. This is the tax Jev removes."""
    cleaned = text.strip().strip("`\"'.").strip().lower()
    if cleaned in allowed:
        return cleaned
    hits = [a for a in allowed if a in cleaned.replace("-", "_").split()]
    return hits[0] if len(hits) == 1 else None
