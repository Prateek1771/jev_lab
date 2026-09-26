"""Backend plumbing that became identical in three projects. Not UI (core/), not settings (config/).
A project with different needs writes its own instead of adding flags here."""

import time
from functools import lru_cache

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import var_child_runnable_config
from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter
from openrouter.utils import BackoffStrategy, RetryConfig

from config import settings
from config.telemetry import langfuse
from core.run import Run
from shared.parse import parse_label


# --- Jev: OpenRouter's Decisions API ------------------------------------------------------

def decide(state, questions: dict) -> tuple[dict, float]:
    """One Decisions request. Returns (response body, latency of the HTTP call alone, in ms)."""
    t0 = time.perf_counter()
    r = httpx.post(
        settings.JEV_URL,
        headers=settings.openrouter_headers(),
        json={"model": settings.JEV_MODEL, "state": state, "questions": questions},
        timeout=settings.HTTP_TIMEOUT_S,
    )
    latency = (time.perf_counter() - t0) * 1000
    r.raise_for_status()
    return r.json(), latency


# --- Baseline chat model -----------------------------------------------------------------

# One attempt, no backoff. ChatOpenRouter(max_retries=0) does NOT do this: it then passes
# no retry config, and the openrouter SDK falls back to retrying for up to an hour (Phase 1, §6).
NO_RETRY = RetryConfig("none", BackoffStrategy(0, 0, 1, 0), retry_connection_errors=False)


@lru_cache(maxsize=8)   # one client per (model, max_tokens, reasoning): the baseline, plus project 05's three tiers
def chat_model(model: str | None = None, max_tokens: int | None = None, reasoning_effort: str | None = None) -> ChatOpenRouter:
    api_key = settings.require(settings.OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    return ChatOpenRouter(
        model=model or settings.BASELINE_MODEL,
        api_key=api_key,
        temperature=settings.BASELINE_TEMPERATURE,
        max_tokens=max_tokens or settings.BASELINE_MAX_TOKENS,
        reasoning={"effort": reasoning_effort} if reasoning_effort else None,   # thinking models only (05's balanced tier)
        # timeout_ms is milliseconds; ChatOpenRouter's own `timeout=` is milliseconds too.
        client=OpenRouter(api_key=api_key, timeout_ms=settings.HTTP_TIMEOUT_S * 1000, retry_config=NO_RETRY),
    )


# --- Traced calls: one Langfuse generation per model call, WITH its cost --------------------
# Copied into 06, 07 and 08 before Phase 8's fixes; the third copy moved them here. With tracing off
# (projects 01-05, and every test) the observation is a no-op and these are plain calls.

def decide_traced(name: str, state, questions: dict) -> tuple[dict, dict]:
    """One Decisions call as one generation. Returns (answers, metadata incl. cost, None if unreported)."""
    with langfuse().start_as_current_observation(
        name=name, as_type="generation", model=settings.JEV_MODEL, input={"state": state, "questions": questions},
    ) as obs:
        body, latency = decide(state, questions)
        usage = body.get("usage") or {}
        meta = {"model": body.get("model", settings.JEV_MODEL), "latency_ms": latency,
                "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                "cost_usd": usage.get("cost"), "id": body.get("id")}
        obs.update(model=meta["model"], output=body["answers"],
                   usage_details={"input": meta["input_tokens"], "output": meta["output_tokens"]},
                   cost_details={"total": meta["cost_usd"]} if meta["cost_usd"] is not None else None,
                   metadata={"latency_ms": round(latency), "openrouter_id": meta["id"]})
        return body["answers"], meta


def metered_call(name: str, llm, messages: list) -> tuple[object, dict]:
    """Invoke one chat model (plain, structured, or with tools) as one generation, with cost.
    callbacks=[]: a graph's Langfuse handler would otherwise log the same call again, tokens but no cost."""
    with langfuse().start_as_current_observation(
        name=name, as_type="generation", model=settings.BASELINE_MODEL,
        input=[{"role": m.type, "content": m.content} for m in messages],
    ) as obs:
        t0 = time.perf_counter()
        # callbacks=[] alone is not enough: a bind_tools model (RunnableBinding) still inherits the graph's
        # handler from the parent run's context and was logged twice (06 and 16 traces, found in Phase 16).
        token = var_child_runnable_config.set(None)
        try:
            out = llm.invoke(messages, config={"callbacks": []})
        finally:
            var_child_runnable_config.reset(token)
        latency = (time.perf_counter() - t0) * 1000
        msg = out["raw"] if isinstance(out, dict) else out     # structured output keeps the raw message
        usage, meta = msg.usage_metadata or {}, msg.response_metadata or {}
        call = {"model": meta.get("model_name", settings.BASELINE_MODEL), "latency_ms": latency,
                "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                "cost_usd": meta.get("cost"), "finish_reason": meta.get("finish_reason")}
        obs.update(model=call["model"],
                   output=out["parsed"] if isinstance(out, dict) else (getattr(msg, "tool_calls", None) or msg.content),
                   usage_details={"input": call["input_tokens"], "output": call["output_tokens"]},
                   cost_details={"total": call["cost_usd"]} if call["cost_usd"] is not None else None,
                   metadata={"latency_ms": round(latency), "finish_reason": call["finish_reason"]})
        return out, call


# --- Plain-prompt baseline: free text, parsed. Was a copy in 01, 03 and 04; 07 would have been the fourth ---

def ask_plain(system: str, user: str, allowed: set[str]) -> Run:
    msg, call = metered_call("baseline.plain", chat_model(), [SystemMessage(system), HumanMessage(user)])
    text = msg.content if isinstance(msg.content, str) else str(msg.content)
    return Run(
        variant="baseline",
        model=call["model"],
        label=parse_label(text, allowed),
        confidence=None,
        latency_ms=call["latency_ms"],
        input_tokens=call["input_tokens"],
        output_tokens=call["output_tokens"],
        cost_usd=call["cost_usd"],  # OpenRouter's usage.cost, surfaced by ChatOpenRouter
        raw={"text": text},
    )


# --- Structured-output baseline: the strongest cheap alternative to Jev -------------------

def label_schema(labels: list[str]) -> dict:
    return {
        "title": "answer",
        "type": "object",
        "properties": {"label": {"type": "string", "enum": labels}},
        "required": ["label"],
        "additionalProperties": False,
    }


def ask_structured(system: str, user: str, labels: list[str]) -> Run:
    """Same prompt as the plain baseline, but the provider must return {"label": <one of labels>}."""
    llm = chat_model().with_structured_output(
        label_schema(labels), method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("baseline.structured", llm, [SystemMessage(system), HumanMessage(user)])

    raw, parsed = out["raw"], out["parsed"]
    # Don't trust the schema blindly: a provider that ignores `strict` can still send anything.
    label = parsed.get("label") if isinstance(parsed, dict) else None
    return Run(
        variant="structured",
        model=call["model"],
        label=label if label in labels else None,
        confidence=None,
        latency_ms=call["latency_ms"],
        input_tokens=call["input_tokens"],
        output_tokens=call["output_tokens"],
        cost_usd=call["cost_usd"],        # include_raw=True is what keeps this
        raw={"text": raw.content if isinstance(raw.content, str) else str(raw.content),
             "parsing_error": str(out["parsing_error"]) if out["parsing_error"] else None},
    )


# --- One Noul and a threshold in code. Was a copy in 02 and 11; 12 would have been the third ---------

def ask_noul(state, name: str, instructions: str, criteria: dict, threshold: float, yes: str, no: str) -> Run:
    body, latency = decide(state, {name: {"type": "noul", "instructions": instructions, "criteria": criteria}})
    p = float(body["answers"][name]["noul"])   # P(statement is true); Noul has no confidence field
    usage = body.get("usage") or {}
    return Run(
        variant="jev",
        model=body.get("model", settings.JEV_MODEL),
        label=yes if p >= threshold else no,   # the threshold is ours, not Jev's
        confidence=None,
        probability=p,
        latency_ms=latency,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cost_usd=usage.get("cost"),
        raw={"noul": p, "threshold": threshold, "id": body.get("id")},
    )
