"""Every setting in the lab. Nothing outside config/ reads the environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Explicit path: a bare load_dotenv() searches from the caller's directory, and
# streamlit and pytest start from different places. Real env vars still win.
load_dotenv(Path(__file__).parent / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, "").strip() or default


# --- OpenRouter: one key for Jev and the baseline ---
OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY")
HTTP_TIMEOUT_S = 60

# --- Jev (TypeSafe System One, served by OpenRouter's Decisions API) ---
JEV_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = _env("JEV_MODEL", "typesafe/jev-1.13")

# --- Baseline LLM (LangChain ChatOpenRouter) ---
BASELINE_MODEL = _env("BASELINE_MODEL", "google/gemini-3.1-flash-lite")
BASELINE_TEMPERATURE = 0.0
BASELINE_MAX_TOKENS = 50
# No retries for the baseline either: enforced in each project's baseline.py with an explicit
# no-retry client, because ChatOpenRouter(max_retries=0) silently retries for up to an hour.

# --- Model tiers that project 05 routes between (ids and prices checked on OpenRouter 2026-09-25) ---
MODEL_TIERS = {
    "fast": _env("TIER_FAST_MODEL", "google/gemini-3.1-flash-lite"),        # $0.25 in / $1.50 out per M tokens
    "balanced": _env("TIER_BALANCED_MODEL", "google/gemini-3.5-flash"),     # $1.50 / $9
    "frontier": _env("TIER_FRONTIER_MODEL", "anthropic/claude-sonnet-5"),   # $2 / $10
}
TIER_REASONING = {"balanced": _env("TIER_BALANCED_REASONING", "minimal")}
# ^ gemini-3.5-flash thinks by default, and the thinking counts against ANSWER_MAX_TOKENS: in the real test it
#   spent up to 765 of 800 tokens reasoning and the answers were cut off. 'minimal' = 0 reasoning tokens (probed).
ANSWER_MAX_TOKENS = 800   # caps what a tier can spend per answer. Was 400: the real smoke test cut off all three
                          # frontier answers to a legal question (finish_reason=length), and the grader failed them
AGENT_MAX_TOKENS = 300    # project 06: one tool call's arguments (an email body is the longest)
RAG_TOP_K = 6             # project 08: chunks the retriever returns per question
RAG_MAX_KEEP = 4          # ... and the most any filter may pass to the answering model
RERANK_N = 10             # project 09: chunks retrieved, then reranked
RERANK_K = 3              # ... and how many of the reranked chunks the answer gets

# --- Langfuse (OTel-based tracing), self-hosted in docker ---
LANGFUSE_PUBLIC_KEY = _env("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = _env("LANGFUSE_SECRET_KEY")
LANGFUSE_BASE_URL = _env("LANGFUSE_BASE_URL", "http://localhost:3000")

# --- The two UIs link to each other (the "New UI | Streamlit" toggle). 3000 is Langfuse, 3100 is WSL here. ---
WEB_UI_URL = _env("WEB_UI_URL", "http://localhost:3737")
LANGFUSE_TRACING_ENABLED = _env("LANGFUSE_TRACING_ENABLED", "true").lower() == "true"

# --- Deployment. Unset locally: no CORS (the browser goes through Next's /api rewrite), no limits. ---
WEB_ORIGINS = [o.strip() for o in _env("WEB_ORIGINS").split(",") if o.strip()]   # the web UI's URL(s), for CORS
# Caps on the paid POSTs so a public site can't be spammed into a big OpenRouter bill. 0 = no limit.
# render.yaml sets the deployed values.
RUN_LIMIT_PER_IP_HOUR = int(_env("RUN_LIMIT_PER_IP_HOUR", "0"))
RUN_LIMIT_PER_DAY = int(_env("RUN_LIMIT_PER_DAY", "0"))
DATASET_LIMIT_PER_IP_HOUR = int(_env("DATASET_LIMIT_PER_IP_HOUR", "0"))
DATASET_LIMIT_PER_DAY = int(_env("DATASET_LIMIT_PER_DAY", "0"))


def require(value: str, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to config/.env (template: config/.env.example).")
    return value


def openrouter_headers() -> dict:
    return {"Authorization": f"Bearer {require(OPENROUTER_API_KEY, 'OPENROUTER_API_KEY')}"}
