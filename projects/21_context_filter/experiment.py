"""Project 21: context filter. A tool returned a big output; which items does the answer actually need?
Code splits the output into items; Jev judges each item on its own, in parallel; the answer sees only what was kept.
Against: sending everything, an LLM summary first, and a keyword filter ($0). Every answer is graded."""

import json
import operator
import re
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run
from shared.grader import grade
from shared.metrics import precision_recall
from shared.openrouter import chat_model, decide_traced, metered_call

TITLE = "21 · Context Filter"
PRIMITIVE = "Noul per tool-output item (parallel calls) · Noul (grade)"
OUTPUTS = json.loads((Path(__file__).parent / "outputs.json").read_text(encoding="utf-8"))
KEEP = 0.5
LABELS = ["answer", "no_answer"]
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Release blockers": {"output": "github_issues", "question": "Which open bugs are blocking the 2.4 release?",
                         "rubric": "Required: #412 (orders page crash) and #418 (refunds not saved).",
                         "gold": ["#412", "#418"]},
    "Why did CI fail": {"output": "ci_log", "question": "Why did the build fail?",
                        "rubric": "Required: test_order_without_items failed with a TypeError ('NoneType' object is "
                                  "not iterable) in src/orders/list.py, line 88.",
                        "gold": ["L19", "L20"]},
    "Priya's work": {"output": "github_issues", "question": "What is Priya working on right now?",
                     "rubric": "Required: #405 (Safari login), #409 (cart refactor) and #421 (cart totals migration).",
                     "gold": ["#405", "#409", "#421"]},
}
STOP = {"what", "which", "when", "where", "does", "that", "this", "with", "have", "there", "right", "about", "were",
        "from", "into", "they", "your", "long", "many", "working"}
ANSWER_SYSTEM = ("Answer the question using only the tool output below. Cite item ids. "
                 "If it does not contain the answer, reply with exactly NO_ANSWER.")


class State(TypedDict, total=False):
    input: dict
    items: list[dict]
    judgments: Annotated[list[dict], operator.add]   # one per parallel jev_judge
    jev: Run
    keyword_filter: Run
    everything: Run
    llm_summary: Run


def load(state: State) -> State:
    return {"items": OUTPUTS[state["input"]["output"]]}


def fan_out(state: State) -> list:
    q = state["input"]["question"]
    return [Send("jev_judge", {"question": q, "item": it}) for it in state["items"]] + \
        ["keyword_filter", "everything", "llm_summary"]


def jev_judge(payload: dict) -> State:
    a, meta = decide_traced("jev.judge_item", {"question": payload["question"], "item": payload["item"]}, {"needed": {
        "type": "noul", "instructions": "item is needed to answer question",
        "criteria": {"true": "item contains part of the answer, or a fact the answer must use or count",
                     "false": "item is about something else, or only shares words with question"}}})
    return {"judgments": [meta | {"item_id": payload["item"]["id"], "p": float(a["needed"]["noul"])}]}


def _answer(question: str, context) -> tuple[str, dict]:
    msg, call = metered_call("llm.answer", chat_model(None, settings.ANSWER_MAX_TOKENS), [
        SystemMessage(ANSWER_SYSTEM), HumanMessage(json.dumps({"question": question, "tool_output": context}))])
    return (msg.content if isinstance(msg.content, str) else str(msg.content)), call


def _run(variant: str, kept: list[str] | None, text: str, calls: list[dict], answer_call: dict, inp: dict, **raw) -> Run:
    g = grade(inp["question"], inp["rubric"], text)
    p, r = precision_recall(kept, inp.get("gold", [])) if kept is not None else (None, None)
    costs = [c["cost_usd"] for c in calls]
    return Run(variant=variant, model=answer_call["model"], label="no_answer" if text.strip().startswith("NO_ANSWER") else "answer",
               confidence=None, latency_ms=sum(c["latency_ms"] for c in calls),
               input_tokens=sum(c["input_tokens"] for c in calls), output_tokens=sum(c["output_tokens"] for c in calls),
               cost_usd=None if any(c is None for c in costs) else sum(costs), quality=g["quality"],
               raw=raw | {"answer": text, "finish_reason": answer_call.get("finish_reason"), "kept": kept,
                          "precision": p, "recall": r, "context_tokens": answer_call["input_tokens"],
                          "grade_cost": g["cost_usd"]})


def jev_answer(state: State) -> State:
    js, inp = state["judgments"], state["input"]
    keep = {j["item_id"] for j in js if j["p"] >= KEEP}
    kept = [it for it in state["items"] if it["id"] in keep]   # original order
    text, call = _answer(inp["question"], kept)
    judge_calls = [{k: j[k] for k in ("latency_ms", "input_tokens", "output_tokens", "cost_usd")} for j in js]
    run = _run("jev", [it["id"] for it in kept], text, judge_calls + [call], call, inp,
               item_p={j["item_id"]: round(j["p"], 2) for j in js},   # every item's P: re-tune KEEP offline
               reason=f"kept {len(kept)} of {len(state['items'])} items")
    run.latency_ms -= sum(c["latency_ms"] for c in judge_calls) - max((c["latency_ms"] for c in judge_calls), default=0)
    return {"jev": run}   # the judges ran in parallel: their wall time counts once


def keyword_filter_node(state: State) -> State:
    """grep for the question's words: free, and blind to meaning."""
    inp = state["input"]
    words = {w for w in re.findall(r"[a-z0-9.]+", inp["question"].lower()) if len(w) > 3 and w not in STOP}
    kept = [it for it in state["items"] if words & set(re.findall(r"[a-z0-9.]+", json.dumps(it).lower()))]
    text, call = _answer(inp["question"], kept)
    return {"keyword_filter": _run("keyword_filter", [it["id"] for it in kept], text, [call], call, inp,
                                   reason=f"kept {len(kept)} of {len(state['items'])} items")}


def everything_node(state: State) -> State:
    inp = state["input"]
    text, call = _answer(inp["question"], state["items"])
    return {"everything": _run("everything", [it["id"] for it in state["items"]], text, [call], call, inp,
                               reason=f"all {len(state['items'])} items")}


def llm_summary_node(state: State) -> State:
    """Compress first: the LLM reads everything once and writes the relevant part; the answer reads that."""
    inp = state["input"]
    msg, s_call = metered_call("llm.summarize", chat_model(None, settings.ANSWER_MAX_TOKENS), [
        SystemMessage("Summarize only the parts of this tool output that matter for the question. Keep item ids, "
                      "numbers and names exactly."),
        HumanMessage(json.dumps({"question": inp["question"], "tool_output": state["items"]}))])
    summary = msg.content if isinstance(msg.content, str) else str(msg.content)
    text, call = _answer(inp["question"], summary)
    return {"llm_summary": _run("llm_summary", None, text, [s_call, call], call, inp, summary=summary,
                                reason="LLM summary, then answer")}


def build_graph():
    g = StateGraph(State)
    g.add_node("load", load)
    g.add_node("jev_judge", jev_judge)
    g.add_node("jev_answer", jev_answer)
    g.add_node("keyword_filter", keyword_filter_node)
    g.add_node("everything", everything_node)
    g.add_node("llm_summary", llm_summary_node)
    g.add_edge(START, "load")
    g.add_conditional_edges("load", fan_out, ["jev_judge", "keyword_filter", "everything", "llm_summary"])
    g.add_edge("jev_judge", "jev_answer")
    for name in ("jev_answer", "keyword_filter", "everything", "llm_summary"):
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    handler = langchain_handler()
    with propagate_attributes(trace_name=TITLE, tags=["21_context_filter"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()
    tid = trace_id(handler)
    return Result(runs={v: out[v] for v in ("jev", "keyword_filter", "everything", "llm_summary")},
                  trace_url=trace_url(tid), trace_id=tid)
