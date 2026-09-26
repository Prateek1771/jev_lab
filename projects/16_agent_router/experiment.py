"""Project 16: agent router. Which agent should take this request, and which of its tools does it need?
Jev: a Choice over agents, then a Choice over THAT agent's tools (two small decisions, traced). Against: an LLM
router picking agent/tool from the whole tree in one call, and one flat agent with every tool bound."""

import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run
from shared.openrouter import chat_model, decide_traced, metered_call

from .agents import AGENTS, TOOL_AGENT

TITLE = "16 · Agent Router"
PRIMITIVE = "Choice (agent) → Choice (that agent's tool)"
LABELS = list(AGENTS)   # the agent; getting the tool right too is the per-row metric "tool_accuracy"
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "'Refund' in a code question": {"request": "The refund endpoint returns a 500. Where is it implemented?",
                                    "tool": "search_code"},
    "Reset already failed": {"request": "The password reset email never arrives, I've tried three times today.",
                             "tool": "create_ticket"},
    "A page to summarize": {"request": "Give me the gist of https://blog.example.com/eu-ai-act-timeline",
                            "tool": "summarize_url"},
}

PAIRS = [f"{a}/{t}" for a, (_, tools) in AGENTS.items() for t in tools]
TREE = "\n".join(f"- {a}: {d}\n" + "\n".join(f"    - {t}: {td}" for t, td in tools.items())
                 for a, (d, tools) in AGENTS.items())
FLAT_TOOLS = [{"type": "function", "function": {
    "name": t, "description": td,
    "parameters": {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]}}}
    for _, (_, tools) in AGENTS.items() for t, td in tools.items()]


class State(TypedDict, total=False):
    input: dict
    jev: Run
    llm_agent_router: Run
    flat_agent: Run


def _run(variant: str, model: str, tool: str | None, gold: str, calls: list[dict], **raw) -> Run:
    agent = TOOL_AGENT.get(tool)
    return Run(variant=variant, model=model, label=agent, confidence=raw.pop("confidence", None),
               latency_ms=sum(c["latency_ms"] for c in calls),
               input_tokens=sum(c["input_tokens"] for c in calls), output_tokens=sum(c["output_tokens"] for c in calls),
               cost_usd=None if any(c["cost_usd"] is None for c in calls) else sum(c["cost_usd"] for c in calls),
               raw=raw | {"tool": tool, "tool_accuracy": float(tool == gold),
                          "reason": f"{agent} → {tool}" if tool else "no tool chosen"})


def jev_node(state: State) -> State:
    """Two decisions, each with only the options that exist at that level. The second one sees the first's
    answer, never the gold tool."""
    request = state["input"]["request"]
    a1, m1 = decide_traced("jev.agent", {"request": request}, {"agent": {
        "type": "choice", "instructions": "Which agent should handle request?",
        "criteria": {a: d for a, (d, _) in AGENTS.items()}}})
    agent = a1["agent"]["choice"]
    a2, m2 = decide_traced("jev.tool", {"request": request, "agent": agent}, {"tool": {
        "type": "choice", "instructions": "Which of agent's tools does request need?",
        "criteria": AGENTS[agent][1]}})
    tool = a2["tool"]["choice"]
    return {"jev": _run("jev", m1["model"], tool, state["input"]["tool"], [m1, m2],
                        confidence=min(float(a1["agent"]["confidence"]), float(a2["tool"]["confidence"])),
                        agent_confidence=round(float(a1["agent"]["confidence"]), 2),
                        tool_confidence=round(float(a2["tool"]["confidence"]), 2))}


def llm_agent_router_node(state: State) -> State:
    llm = chat_model(None, settings.AGENT_MAX_TOKENS).with_structured_output(
        {"title": "route", "type": "object", "properties": {"route": {"type": "string", "enum": PAIRS}},
         "required": ["route"], "additionalProperties": False},
        method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("llm.route", llm, [
        SystemMessage(f"Route the request to one agent and the tool the request needs:\n{TREE}\n"
                      "Answer agent/tool."), HumanMessage(state["input"]["request"])])
    route = out["parsed"].get("route") if isinstance(out["parsed"], dict) else None
    tool = route.split("/")[1] if route in PAIRS else None
    return {"llm_agent_router": _run("llm_agent_router", call["model"], tool, state["input"]["tool"], [call])}


def flat_agent_node(state: State) -> State:
    """The 'one big agent': every tool from every agent bound at once; whichever it calls decides the agent."""
    llm = chat_model(None, settings.AGENT_MAX_TOKENS).bind_tools(FLAT_TOOLS, parallel_tool_calls=False)
    msg, call = metered_call("llm.flat_agent", llm, [
        SystemMessage("You are a company assistant. Call the one tool the request needs."),
        HumanMessage(state["input"]["request"])])
    tool = msg.tool_calls[0]["name"] if getattr(msg, "tool_calls", None) else None
    return {"flat_agent": _run("flat_agent", call["model"], tool if tool in TOOL_AGENT else None,
                               state["input"]["tool"], [call])}


NODES = {"jev": jev_node, "llm_agent_router": llm_agent_router_node, "flat_agent": flat_agent_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    handler = langchain_handler()
    with propagate_attributes(trace_name=TITLE, tags=["16_agent_router"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()
    tid = trace_id(handler)
    return Result(runs={v: out[v] for v in NODES}, trace_url=trace_url(tid), trace_id=tid)
