"""Plain-prompt baseline for project 02: a chat LLM answers yes/no in free text, and we parse it."""

import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from core.run import Run
from shared.openrouter import chat_model   # moved to shared/ in Phase 3


def parse_yes_no(text: str) -> bool | None:
    """True/False for a clear yes/no; None when the reply says both, neither, or something else."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    yes, no = "yes" in words, "no" in words
    return None if yes == no else yes


def ask_yes_no(system: str, user: str, yes: str, no: str) -> Run:
    t0 = time.perf_counter()
    msg = chat_model().invoke([SystemMessage(system), HumanMessage(user)])
    latency = (time.perf_counter() - t0) * 1000

    text = msg.content if isinstance(msg.content, str) else str(msg.content)
    answer = parse_yes_no(text)
    usage = msg.usage_metadata or {}
    meta = msg.response_metadata or {}
    return Run(
        variant="baseline",
        model=meta.get("model_name", settings.BASELINE_MODEL),
        label=None if answer is None else (yes if answer else no),
        confidence=None,
        latency_ms=latency,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cost_usd=meta.get("cost"),
        raw={"text": text},
    )
