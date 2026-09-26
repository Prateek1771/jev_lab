"""LLM side of project 10: the usual LLM-as-judge, the whole answer and every source in ONE prompt."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from shared.openrouter import chat_model, metered_call

from .claims import VERDICTS

JUDGE_SYSTEM = (
    "You check a support answer against the sources it cites in [brackets]. Reply with one label:\n"
    "supported: every sentence is stated by a source it cites, including every number and condition;\n"
    "contradicted: some sentence is made false by a source it cites;\n"
    "insufficient: some sentence has no citation, cites an id that is not among the sources, "
    "or cites a source that does not say it."
)


def judge(question: str, answer: str, sources: list[dict]) -> tuple[str | None, str, dict]:
    """(label or None if outside the enum, its reason, call). Same checks as Jev's path, described in words."""
    llm = chat_model(None, settings.AGENT_MAX_TOKENS).with_structured_output(
        {"title": "verdict", "type": "object",
         "properties": {"reason": {"type": "string"}, "label": {"type": "string", "enum": VERDICTS}},
         "required": ["reason", "label"], "additionalProperties": False},
        method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("llm.judge", llm, [SystemMessage(JUDGE_SYSTEM), HumanMessage(json.dumps(
        {"question": question, "answer": answer, "sources": [{"id": s["id"], "text": s["text"]} for s in sources]}))])
    parsed = out["parsed"] if isinstance(out["parsed"], dict) else {}
    label = parsed.get("label")
    return (label if label in VERDICTS else None), str(parsed.get("reason", "")), call
