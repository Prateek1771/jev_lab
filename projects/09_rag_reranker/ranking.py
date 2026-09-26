"""Ordering and how to score an ordering. Pure: no I/O, no model calls."""

import math


def jev_order(scores: list[dict], retrieved: list[str], key: str = "score") -> list[str]:
    """Highest Jev value first; ties keep the retriever's order (not a second question, as the reference does).
    key="score" is the expected relevance (0..2); key="p_top" is P(directly answers). They can disagree:
    50% irrelevant + 50% direct scores 1.0, exactly like 100% background."""
    rank = {cid: i for i, cid in enumerate(retrieved)}
    by_id = {s["id"]: s for s in scores}
    return sorted(retrieved, key=lambda cid: (-by_id[cid][key] if cid in by_id else 0.0, rank[cid]))


def ndcg_at_k(order: list[str], gold: dict[str, int], k: int) -> float | None:
    """Graded relevance, discounted by position. 1.0 = the best possible top k. None if nothing is relevant."""
    def dcg(grades):
        return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:k]))
    ideal = dcg(sorted(gold.values(), reverse=True))
    return dcg([gold.get(cid, 0) for cid in order]) / ideal if ideal else None


def mrr(order: list[str], gold: dict[str, int]) -> float | None:
    """1 / rank of the first chunk that directly answers (grade 2). None if no chunk does."""
    if 2 not in gold.values():
        return None
    return next((1 / (i + 1) for i, cid in enumerate(order) if gold.get(cid) == 2), 0.0)
