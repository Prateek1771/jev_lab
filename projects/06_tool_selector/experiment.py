"""Project 06: tool selection. An agent loops: pick the next tool (or stop), write its arguments,
run it, look at the result. Three agents differ only in who picks. The label is the whole trajectory."""

import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run

from . import jev_client, llm, policy
from .tools import TOOLS, run_tool

TITLE = "06 · Tool Selector"
PRIMITIVE = "Choice per step (multi-step, traced)"
LABELS = ["get_weather", "search_web", "calculator", "database", "create_ticket", "send_email",
          "database > calculator", "none", "ask_user"]
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "One tool": {"request": "Is it raining in London right now?"},
    "Two tools": {"request": "What does order A-104 cost in total with shipping, plus 20% VAT on all of it?"},
    "No tool": {"request": "Thanks, that's everything for today!"},
    "Unclear": {"request": "Send it to him."},
}


class State(TypedDict, total=False):
    input: dict
    jev: dict          # each agent's progress: {"steps": [...], "calls": [...], "stop": None | str, ...}
    llm_selector: dict
    tool_calling: dict


def _fresh() -> dict:
    return {"steps": [], "calls": [], "stop": None}


def _observations(p: dict) -> list[dict]:
    """What every selector sees of earlier steps: tool, arguments, result. Nothing else."""
    return [{"tool": s["tool"], "args": s["args"], "result": s["result"]} for s in p["steps"]]


def _selector_step(p: dict, request: str, pick) -> dict:
    """One loop turn for the two selector agents: pick, gate, then (for a tool) write args and run it."""
    choice, conf, call = pick(request, _observations(p))
    step, reason = policy.next_step(choice, conf)
    calls = p["calls"] + [call]
    if step not in TOOLS:
        return p | {"calls": calls, "stop": step, "stop_reason": reason, "last_conf": conf}
    args, args_call = llm.write_args(step, request, _observations(p))
    s = {"tool": step, "args": args, "result": run_tool(step, args), "confidence": conf, "reason": reason}
    return p | {"steps": p["steps"] + [s], "calls": calls + [args_call]}


def _jev_pick(request, observations):
    a = jev_client.pick_tool(request, observations)
    return a["choice"], a["confidence"], a


def _llm_pick(request, observations):
    choice, call = llm.pick_tool(request, observations)
    return choice, None, call


def jev_node(state: State) -> State:
    return {"jev": _selector_step(state.get("jev") or _fresh(), state["input"]["request"], _jev_pick)}


def llm_selector_node(state: State) -> State:
    return {"llm_selector": _selector_step(state.get("llm_selector") or _fresh(), state["input"]["request"], _llm_pick)}


def tool_calling_node(state: State) -> State:
    """Native tool calling: the model picks the tool and writes its arguments in the same message."""
    p = state.get("tool_calling") or _fresh() | {"messages": [HumanMessage(state["input"]["request"])]}
    return {"tool_calling": _native_step(p)}


def _native_step(p: dict) -> dict:
    msg, call = llm.native_step(p["messages"])
    calls = p["calls"] + [call]
    if not msg.tool_calls:
        return p | {"calls": calls, "stop": "finish", "stop_reason": "final answer: no tool call in its last message"}
    tc = msg.tool_calls[0]
    if tc["name"] == "ask_user":
        return p | {"calls": calls, "stop": "ask_user", "stop_reason": tc["args"].get("question", "")}
    result = run_tool(tc["name"], tc["args"]) if tc["name"] in TOOLS else f"error: no tool {tc['name']}"
    s = {"tool": tc["name"], "args": tc["args"], "result": result, "confidence": None, "reason": "tool call"}
    return p | {"steps": p["steps"] + [s], "calls": calls,
                "messages": p["messages"] + [msg, ToolMessage(result, tool_call_id=tc["id"])]}


NODES = {"jev": jev_node, "llm_selector": llm_selector_node, "tool_calling": tool_calling_node}


def _again(name: str):
    """The loop edge: back to the same node until the agent stops, or MAX_STEPS tool calls."""
    return lambda s: END if s[name]["stop"] or len(s[name]["steps"]) >= policy.MAX_STEPS else name


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():   # three agents in parallel, each looping on its own node and state key
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_conditional_edges(name, _again(name), [name, END])
    return g.compile()


GRAPH = build_graph()


def _total(costs) -> float | None:
    costs = list(costs)
    return None if any(c is None for c in costs) else sum(costs)


def _run(variant: str, p: dict) -> Run:
    tools = [s["tool"] for s in p["steps"]]
    confs = [c for c in [s["confidence"] for s in p["steps"]] + [p.get("last_conf")] if c is not None]
    return Run(
        variant=variant,
        model=next((c["model"] for c in p["calls"] if "model" in c), settings.BASELINE_MODEL),  # Jev's snapshot
        label=policy.trajectory(tools, p["stop"]),
        confidence=min(confs) if confs else None,   # the weakest pick decides how far to trust the run
        latency_ms=sum(c["latency_ms"] for c in p["calls"]),
        input_tokens=sum(c["input_tokens"] for c in p["calls"]),
        output_tokens=sum(c["output_tokens"] for c in p["calls"]),
        cost_usd=_total(c["cost_usd"] for c in p["calls"]),
        raw={"steps": p["steps"], "stop": p["stop"] or f"gave up after {policy.MAX_STEPS} tool calls",
             "reason": p.get("stop_reason") or ("" if p["stop"] else "never decided it was done"),
             "calls": len(p["calls"])},
    )


def run_experiment(inp: dict) -> Result:
    handler = langchain_handler()   # traces the graph, each loop turn as a node span; our generations nest inside
    with propagate_attributes(trace_name=TITLE, tags=["06_tool_selector"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()   # Streamlit is long-lived: flush now so the trace link works on this click
    tid = trace_id(handler)
    return Result(runs={name: _run(name, out[name]) for name in NODES}, trace_url=trace_url(tid), trace_id=tid)
