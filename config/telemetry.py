"""One Langfuse client for the process. Langfuse v4 is built on OpenTelemetry:
every observation (manual or from the LangChain handler) is an OTel span exported over OTLP."""

from functools import lru_cache

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from config import settings


@lru_cache(maxsize=1)
def langfuse() -> Langfuse:
    # Missing keys must switch tracing OFF here. Langfuse only logs "disabled":
    # its OTel exporter still posts every span, and a running server answers 401.
    has_keys = bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY or None,
        secret_key=settings.LANGFUSE_SECRET_KEY or None,
        base_url=settings.LANGFUSE_BASE_URL,
        tracing_enabled=settings.LANGFUSE_TRACING_ENABLED and has_keys,
    )


def langchain_handler() -> CallbackHandler:
    """A fresh handler per graph run; it traces the graph and every node as spans.
    Bound to the client above by public key, so it never builds a second client from env."""
    langfuse()
    return CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY or None)


def trace_id(handler: CallbackHandler) -> str | None:
    """The handler's trace id, or None. With tracing off it reports 32 zeros (OTel's invalid id), not None."""
    tid = handler.last_trace_id
    return tid if tid and tid.strip("0") else None


def trace_url(trace_id: str | None) -> str | None:
    if not trace_id:
        return None
    try:
        return langfuse().get_trace_url(trace_id=trace_id)  # one API call, then cached
    except Exception:
        return None  # a broken link must never break an experiment


def batch_session(session_id: str):
    """Every trace created inside shares one Langfuse session: a dataset run is one session.
    Merges with the project's own trace_name/tags (checked), it does not replace them."""
    return propagate_attributes(session_id=session_id)


def score_correct(trace_id: str | None, name: str, correct: bool, comment: str = "") -> None:
    """0/1 NUMERIC score on a trace, so Langfuse can average it into accuracy."""
    if not trace_id:
        return
    try:
        langfuse().create_score(trace_id=trace_id, name=name, value=float(correct),
                                data_type="NUMERIC", comment=comment or None)
    except Exception:
        pass  # a lost score must never lose the batch row it describes
