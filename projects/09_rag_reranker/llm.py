"""LLM side of project 09: the one-prompt LLM ranker, and the answering step every variant shares."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from shared.openrouter import chat_model, metered_call

NO_ANSWER = "NO_ANSWER"
ANSWER_SYSTEM = (
    "Answer the customer's question using ONLY the context chunks. Cite the chunk ids you used in [brackets]. "
    f"If the chunks do not contain the answer, reply with exactly {NO_ANSWER} and nothing else."
)
RANK_SYSTEM = ("Rank the retrieved help-centre chunks by how well each answers the question, best first. "
               "Return every chunk id exactly once.")


def _context(chunks: list[dict]) -> str:
    return json.dumps([{"id": c["id"], "text": c["text"]} for c in chunks])


def rank(question: str, chunks: list[dict]) -> tuple[list[str], dict]:
    """The usual LLM reranker: all chunks in ONE prompt. Its list is repaired, not trusted: unknown ids and
    duplicates are dropped, and any id it left out is appended in the retriever's order."""
    ids = [c["id"] for c in chunks]
    llm = chat_model(None, settings.AGENT_MAX_TOKENS).with_structured_output(
        {"title": "ranking", "type": "object",
         "properties": {"order": {"type": "array", "items": {"type": "string", "enum": ids}}},
         "required": ["order"], "additionalProperties": False},
        method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("llm.rank", llm, [
        SystemMessage(RANK_SYSTEM), HumanMessage(json.dumps({"question": question, "chunks": _context(chunks)}))])
    got = out["parsed"].get("order", []) if isinstance(out["parsed"], dict) else []
    order = [i for i in dict.fromkeys(got) if i in ids]
    return order + [i for i in ids if i not in order], call


def answer(question: str, chunks: list[dict]) -> tuple[str, dict]:
    """The same model, prompt and cap for every variant: only which chunks come first differs."""
    msg, call = metered_call("llm.answer", chat_model(None, settings.ANSWER_MAX_TOKENS), [
        SystemMessage(ANSWER_SYSTEM), HumanMessage(json.dumps({"question": question, "context": _context(chunks)}))])
    return (msg.content if isinstance(msg.content, str) else str(msg.content)), call
