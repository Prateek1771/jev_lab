"""Project 11's free baseline: the deny-list of phrases most injection filters start with. No model, $0."""

import re

DENY = {name: re.compile(p, re.I) for name, p in {
    "ignore previous instructions":
        r"\b(ignore|forget|disregard)\b.{0,30}\b(previous|prior|above|earlier|all)\b.{0,20}\b(instructions?|rules|prompts?|messages?|emails?)\b",
    "ignore your rules": r"\b(ignore|forget|disregard|drop)\b.{0,20}\b(your|its|the|my)\b.{0,10}\b(rules|instructions|guidelines|policy)\b",
    "system prompt": r"\b(system prompt|hidden prompt|initial instructions)\b",
    "new rules": r"\bnew (rules|instructions)\b",
    "system notice": r"\bsystem (notice|message|override)\b",
    "addresses the AI": r"\b(if you are|note to|message to)\b.{0,20}\b(an? )?(ai|assistant|language model|llm)\b",
    "you are now": r"\byou are now\b",
    "developer mode": r"\bdeveloper mode\b",
    "DAN": r"\bDAN\b",
    "jailbreak": r"\bjailbreak",
    "reveal secrets": r"\b(reveal|print|show|dump)\b.{0,40}\b(password|api key|secret|credentials?)\b",
}.items()}


def match(text: str) -> str | None:
    """The name of the first pattern that hits, or None. Words, not meaning: a paraphrase slips past, a mention
    gets blocked."""
    return next((name for name, p in DENY.items() if p.search(text)), None)
