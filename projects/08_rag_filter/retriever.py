"""A deliberately plain retriever: word overlap over a 20-chunk help centre. Pure, stdlib only.
It is noisy on purpose (any chunk sharing words like "refund" scores), so there is something to filter.
ponytail: word overlap, swap in a vector search behind retrieve() when the corpus outgrows it."""

import json
import re
from pathlib import Path

CORPUS = json.loads((Path(__file__).parent / "corpus.json").read_text(encoding="utf-8"))
STOP = {"a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "if", "in", "is", "it", "my", "of", "on",
        "or", "the", "to", "what", "when", "which", "who", "with", "you", "your", "we", "our", "me", "get", "long"}


def words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP}


def retrieve(question: str, k: int) -> list[dict]:
    """Top k chunks by shared words; ties broken by id so the same question always gets the same chunks."""
    q = words(question)
    scored = sorted(CORPUS, key=lambda c: (-len(q & words(c["text"])), c["id"]))
    return [{"id": c["id"], "source": c["source"], "text": c["text"]} for c in scored[:k]]
