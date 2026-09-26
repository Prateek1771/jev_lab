"""LLM side of project 06: writing a chosen tool's arguments, the LLM tool selector, and the native
tool-calling agent. Every call goes through shared.metered_call: one Langfuse generation WITH its cost."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import settings
from shared.openrouter import chat_model, metered_call

from .policy import STOPS
from .tools import TOOLS


def _llm():
    return chat_model(None, settings.AGENT_MAX_TOKENS)   # the baseline model, with room for an email body


def _context(request: str, observations: list[dict]) -> str:
    return json.dumps({"request": request, "observations": observations})


def write_args(tool: str, request: str, observations: list[dict], tools: dict = TOOLS) -> tuple[dict, dict]:
    """The generative half: arguments for the ONE tool already chosen, forced into that tool's schema."""
    desc, schema, _ = tools[tool]
    llm = _llm().with_structured_output({"title": tool, **schema}, method="json_schema", strict=True,
                                        include_raw=True)
    out, call = metered_call(f"args.{tool}", llm, [
        SystemMessage(f"Write the arguments for the tool {tool} ({desc}) that serve the request. "
                      "Use values from the request and the observations so far; do not invent ids."),
        HumanMessage(_context(request, observations))])
    return (out["parsed"] if isinstance(out["parsed"], dict) else {}), call


SELECT_SYSTEM = ("You are an assistant's planner. Pick what to do next:\n"
                 + "\n".join(f"- {n}: {d}" for n, (d, _, _) in TOOLS.items())
                 + "".join(f"\n- {n}: {d}" for n, d in STOPS.items()))


def pick_tool(request: str, observations: list[dict]) -> tuple[str, dict]:
    """The LLM selector: same options as Jev's Choice, as a structured-output enum. No confidence."""
    options = list(TOOLS) + list(STOPS)
    llm = _llm().with_structured_output(
        {"title": "next", "type": "object", "properties": {"next": {"type": "string", "enum": options}},
         "required": ["next"], "additionalProperties": False},
        method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("llm.pick_tool", llm, [SystemMessage(SELECT_SYSTEM),
                                                HumanMessage(_context(request, observations))])
    choice = out["parsed"].get("next") if isinstance(out["parsed"], dict) else None
    return (choice if choice in options else "ask_user"), call   # outside the enum: ask, don't guess


# --- the native tool-calling agent: the model picks the tool AND writes its arguments in one message ---

def native_tools(tools: dict) -> list[dict]:
    """The tools as function specs, plus ask_user so the native agent has the same way out as the selectors."""
    return [{"type": "function", "function": {"name": n, "description": d, "parameters": s}}
            for n, (d, s, _) in tools.items()] + [
        {"type": "function", "function": {"name": "ask_user", "description": STOPS["ask_user"],
                                          "parameters": {"type": "object", "properties": {"question": {"type": "string"}},
                                                         "required": ["question"]}}}]


NATIVE_TOOLS = native_tools(TOOLS)
NATIVE_SYSTEM = "You are a helpful assistant. Use a tool when one is needed; answer directly when none is."


def native_step(messages: list, tools: list = NATIVE_TOOLS, system: str = NATIVE_SYSTEM, model=None,
                name: str = "llm.native_agent") -> tuple[AIMessage, dict]:
    """Defaults are this project's agent; project 24 passes its own tools, policy and model."""
    llm = (model or _llm()).bind_tools(tools, parallel_tool_calls=False)
    return metered_call(name, llm, [SystemMessage(system), *messages])
