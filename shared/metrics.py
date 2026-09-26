"""Set-overlap metrics. Was a copy in 08 (kept chunks) and 15 (flagged rules); 21 (kept items) was the third."""


def precision_recall(picked: list[str], gold: list[str]) -> tuple[float | None, float | None]:
    """Of what was picked, how much was relevant; of what was relevant, how much was picked.
    None when there's nothing to divide by: never pretend 0/0 is a score."""
    hit = len(set(picked) & set(gold))
    return (hit / len(picked) if picked else None), (hit / len(gold) if gold else None)
