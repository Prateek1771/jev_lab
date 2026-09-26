"""shared/openrouter.py, offline. The ChatOpenRouter tests use the real library code path with
only the HTTP transport mocked, so they break if a library upgrade changes what we rely on."""

import json
import time

import httpx
import pytest
from langchain_openrouter import ChatOpenRouter
from openrouter import OpenRouter

from config import settings
from shared import openrouter as shared


def mock_model(content: str, cost=0.000039, seen: dict | None = None) -> ChatOpenRouter:
    def handler(request: httpx.Request):
        if seen is not None:
            seen["body"] = json.loads(request.content)
        usage = {"prompt_tokens": 120, "completion_tokens": 6, "total_tokens": 126} | ({"cost": cost} if cost else {})
        return httpx.Response(200, json={
            "id": "gen-1", "model": "google/gemini-3.1-flash-lite", "object": "chat.completion", "created": 1,
            "system_fingerprint": None, "usage": usage,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]})

    client = OpenRouter(api_key="sk-or-test", retry_config=shared.NO_RETRY,
                        client=httpx.Client(transport=httpx.MockTransport(handler)))
    return ChatOpenRouter(model="google/gemini-3.1-flash-lite", api_key="sk-or-test", client=client)


LABELS = ["billing", "technical"]


def test_structured_valid_label_keeps_cost_and_sends_strict_schema(monkeypatch):
    seen = {}
    monkeypatch.setattr(shared, "chat_model", lambda: mock_model('{"label": "billing"}', seen=seen))
    run = shared.ask_structured("sys", "charged twice", LABELS)
    assert (run.variant, run.label) == ("structured", "billing")
    assert run.cost_usd == 0.000039 and run.input_tokens == 120   # include_raw=True keeps the raw message
    fmt = seen["body"]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["properties"]["label"]["enum"] == LABELS


@pytest.mark.parametrize("content", [
    '{"label": "finance"}',    # a provider that ignores strict can still invent a label
    'billing',                 # not JSON at all
    '{"team": "billing"}',     # wrong key
])
def test_structured_bad_output_is_invalid_not_guessed(monkeypatch, content):
    monkeypatch.setattr(shared, "chat_model", lambda: mock_model(content))
    run = shared.ask_structured("sys", "x", LABELS)
    assert run.label is None
    assert run.cost_usd == 0.000039   # a wrong answer still cost money, and the table must say so


def test_chatopenrouter_keeps_cost():
    """What the plain baselines rely on: ChatOpenRouter copies usage.cost into response_metadata."""
    msg = mock_model("billing").invoke("hi")
    assert msg.response_metadata["cost"] == 0.000039
    assert msg.usage_metadata["input_tokens"] == 120


def test_chat_model_has_no_retries_and_ms_timeout(monkeypatch):
    """Regression (Phase 1 hang): ChatOpenRouter(max_retries=0) falls back to the SDK's 1-hour retry
    loop, and ChatOpenRouter's `timeout` is milliseconds."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    shared.chat_model.cache_clear()
    cfg = shared.chat_model().client.sdk_configuration
    shared.chat_model.cache_clear()
    assert cfg.retry_config.strategy == "none"
    assert cfg.timeout_ms == settings.HTTP_TIMEOUT_S * 1000


def test_fails_fast_on_dead_server():
    dead = OpenRouter(api_key="sk-or-test", server_url="http://127.0.0.1:9", timeout_ms=2000, retry_config=shared.NO_RETRY)
    llm = ChatOpenRouter(model="x", api_key="sk-or-test", client=dead)
    t0 = time.perf_counter()
    with pytest.raises(Exception):
        llm.invoke("hi")
    assert time.perf_counter() - t0 < 10   # one attempt; the SDK default would keep retrying


def test_missing_key_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    with pytest.raises(RuntimeError, match="config/.env"):
        settings.openrouter_headers()


class FakeLLM:
    def __init__(self, out):
        self.out, self.config = out, None

    def invoke(self, messages, config=None):
        self.config = config
        return self.out


def test_metered_call_reports_cost_and_bypasses_the_graph_handler():
    """Moved here from project 06 when llm_call became shared.metered_call (third copy: 06, 07 via ask_*, 08)."""
    from langchain_core.messages import AIMessage
    msg = AIMessage("hi", usage_metadata={"input_tokens": 9, "output_tokens": 2, "total_tokens": 11},
                    response_metadata={"cost": 0.00003, "model_name": "m", "finish_reason": "length"})
    fake = FakeLLM(msg)
    _, c = shared.metered_call("t", fake, [])
    assert (c["cost_usd"], c["input_tokens"], c["model"], c["finish_reason"]) == (0.00003, 9, "m", "length")
    assert fake.config == {"callbacks": []}   # logged once, by our generation, with cost


def test_decide_traced_returns_answers_and_cost(monkeypatch):
    body = {"answers": {"q": {"noul": 0.7}}, "model": "typesafe/jev-1.13-20260917", "id": "gen-1",
            "usage": {"input_tokens": 50, "output_tokens": 0, "cost": 0.0000021}}
    monkeypatch.setattr(shared, "decide", lambda state, questions: (body, 90.0))
    a, meta = shared.decide_traced("jev.test", {"x": 1}, {"q": {}})
    assert a == {"q": {"noul": 0.7}} and (meta["cost_usd"], meta["latency_ms"], meta["model"]) == (0.0000021, 90.0, body["model"])


def test_metered_call_is_logged_once_even_for_bound_models():
    """Found in Phase 16's trace: a bind_tools model inside a traced graph showed up twice (our generation, plus
    the graph handler's own), so Langfuse counted its cost twice. metered_call must hide the parent handler."""
    from typing import TypedDict

    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.graph import END, START, StateGraph

    from shared.openrouter import metered_call

    seen = []

    class Count(BaseCallbackHandler):
        def on_chat_model_start(self, *a, **k):
            seen.append(1)

    class S(TypedDict, total=False):
        x: str

    def node(state):
        model = GenericFakeChatModel(messages=iter([AIMessage("hi")])).bind(tools=[{"name": "t"}])
        metered_call("probe", model, [HumanMessage("q")])
        return {"x": "done"}
    g = StateGraph(S)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    g.compile().invoke({}, config={"callbacks": [Count()]})
    assert seen == []
