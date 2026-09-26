"""Project 10, pure: split an answer into claims, check what code can check, and combine the verdicts.
The reference asks a model whether a quote appears in the source. That is string matching, so code does it here;
Jev is only asked the one thing code cannot do: does this source SAY this claim?"""

import re

CITE = re.compile(r"\[([\w.\-]+)\]")
# a sentence ends at . ! ? followed by space (not "$4.99"); citations placed after the full stop stay with it.
# ponytail: a citation mid-sentence followed by a capitalised word also splits; fine for help-centre answers
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?!\[)|(?<=\])\s+(?=[A-Z])")
REPLY_ONLY = re.compile(r"(yes|no)[.!]?", re.I)   # "Yes." answers the question; it asserts nothing to cite
UNSURE = 0.45   # a Jev choice below this confidence proves nothing either way

VERDICTS = ["supported", "contradicted", "insufficient"]
WORST_FIRST = ["contradicted", "insufficient", "supported"]


def split_claims(answer: str) -> list[dict]:
    """[{"text", "cites"}] per sentence, citation marks removed from the text, cites de-duplicated in order."""
    out = []
    for sentence in SENTENCE_END.split(answer.strip()):
        cites = list(dict.fromkeys(CITE.findall(sentence)))
        text = re.sub(r"\s+([.!?,;:])", r"\1", CITE.sub("", sentence)).strip()
        text = re.sub(r"\s{2,}", " ", text)
        if text.strip(".!? ") and not REPLY_ONLY.fullmatch(text):
            out.append({"text": text, "cites": cites})
    return out


def code_check(claim: dict, source_ids: set[str]) -> str | None:
    """What needs no model: a claim with no citation, or one citing a source that was never retrieved
    (a hallucinated citation). None = the citations are real, so Jev must read them."""
    if not claim["cites"]:
        return "uncited"
    if any(c not in source_ids for c in claim["cites"]):
        return "unknown_source"
    return None


def claim_verdict(checks: list[dict]) -> str:
    """checks: Jev's {"choice", "confidence"} for each source this claim cites. One source that supports it is
    enough (a claim may cite a stale page next to the current one); otherwise one that contradicts it decides."""
    sure = [c["choice"] for c in checks if c["confidence"] >= UNSURE]
    if "supports" in sure:
        return "supported"
    if "contradicts" in sure:
        return "contradicted"
    return "insufficient"


def answer_verdict(claim_verdicts: list[str]) -> str:
    """The worst claim decides: one wrong sentence makes the answer wrong."""
    return next((v for v in WORST_FIRST if v in claim_verdicts), "insufficient")

