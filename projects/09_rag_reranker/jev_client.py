"""Jev side of project 09: one relevance Score per chunk, one call per chunk with its own state."""

from shared.openrouter import decide_traced

LEVELS = ["Irrelevant: off-topic, or only shares words with the question",
          "Related background: on the topic, but does not answer the question",
          "Directly answers: states what the question asks"]
QUESTION = {"relevance": {"type": "score", "instructions": "How relevant is chunk to answering question?",
                          "criteria": LEVELS}}


def score_chunk(question: str, chunk: dict) -> dict:
    """One Score per chunk, isolated like 08's judges. Keeps the expected score AND P(directly answers):
    the same score can hide very different distributions (see ranking.py)."""
    a, meta = decide_traced("jev.score_chunk",
                            {"question": question, "chunk": chunk["text"], "source": chunk["source"]}, QUESTION)
    r = a["relevance"]
    probs = {int(k): float(v) for k, v in r["probabilities"].items()}   # JSON keys are strings: "0", "1", "2"
    return meta | {"openrouter_id": meta["id"], "id": chunk["id"], "score": float(r["score"]),
                   "confidence": float(r["confidence"]), "p_top": probs.get(len(LEVELS) - 1, 0.0)}
