"""Jev side of project 10: ONE Choice per (claim, cited source), each call seeing only that pair."""

from shared.openrouter import decide_traced

QUESTION = {"support": {
    "type": "choice", "instructions": "What does source say about claim?",
    "criteria": {"supports": "source states claim, in the same or other words, including every number and condition",
                 "contradicts": "source states something that makes claim false: a different number, condition or rule",
                 "not_addressed": "source is about something else, or says too little to confirm or deny claim"},
}}


def check_pair(claim: str, source: dict) -> dict:
    """The reference asks four questions (support, quote faithful, overclaim, evidence strength) and decides
    on three: the same judgment asked three ways, plus one it never reads. Here it is asked once."""
    a, meta = decide_traced("jev.check_pair", {"claim": claim, "source": source["text"]}, QUESTION)
    s = a["support"]
    return meta | {"openrouter_id": meta["id"], "source_id": source["id"],
                   "choice": s["choice"], "confidence": float(s["confidence"])}
