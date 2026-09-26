"""Project 12, pure: find PII-shaped strings and redact them. Finding a 16-digit number that passes Luhn is code;
deciding whether it is a real person's card or Stripe's test card is judgment, so it is left to the model."""

import re

PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+(\.[\w-]+)+\b"),
    "card": re.compile(r"\b\d(?:[ -]?\d){12,18}\b"),
    "phone": re.compile(r"(?<!\w)(\+\d{1,3}[ -]?)?(\(?\d{2,4}\)?[ -]?){2,4}\d{3,4}(?!\w)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "api_key": re.compile(r"\b(sk-(live|test|proj)?[-_]?[A-Za-z0-9]{16,}|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{30,})\b"),
    "password": re.compile(r"\b(password|passcode|pw)\b\s*(is|:|=)\s*\S+", re.I),
}
ORDER = ["api_key", "email", "ssn", "card", "phone", "password"]   # first kind wins a span


def luhn(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d) * (2 if alt else 1)
        total += n - 9 if n > 9 else n
        alt = not alt
    return total % 10 == 0


def find(text: str) -> list[dict]:
    """[{"kind", "start", "end", "value"}], non-overlapping, in text order."""
    hits, taken = [], []
    for kind in ORDER:
        for m in PATTERNS[kind].finditer(text):
            s, e = m.span()
            digits = re.sub(r"\D", "", m.group())
            if kind == "card" and not (13 <= len(digits) <= 19 and luhn(digits)):
                continue
            if kind == "phone" and not 10 <= len(digits) <= 15:
                continue
            if any(s < te and ts < e for ts, te in taken):
                continue
            taken.append((s, e))
            hits.append({"kind": kind, "start": s, "end": e, "value": m.group()})
    return sorted(hits, key=lambda h: h["start"])


def redact(text: str, hits: list[dict]) -> str:
    for h in sorted(hits, key=lambda h: -h["start"]):
        text = text[:h["start"]] + f"[{h['kind'].upper()}]" + text[h["end"]:]
    return text
