"""Project 10: citation verifier. An answer cites sources in [brackets]; do the cited sources actually say it?
Code splits the answer into claims and catches missing or made-up citations; Jev reads each (claim, cited source)
pair on its own, in parallel. Against: an LLM judging the whole answer in one prompt, and trusting the brackets."""

import json
import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run

from . import jev_client, llm
from .claims import VERDICTS, answer_verdict, claim_verdict, code_check, split_claims

TITLE = "10 · Citation Verifier"
PRIMITIVE = "Choice per (claim, cited source), parallel calls"
LABELS = VERDICTS
SAFETY = {"unsafe": "contradicted", "safe": "supported",   # render_batch: contradictions caught / passed as supported
          "names": ["Contradictions caught", "Contradictions passed as SUPPORTED", "Supported answers flagged"]}
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

_RETURNS = {"id": "returns-window", "text": "Unused items can be returned within 30 days of delivery for a full refund."}
_LABEL = {"id": "returns-label", "text": "Return labels are free for defective items. For change-of-mind returns, "
                                         "$5 is taken off the refund to cover the label."}
EXAMPLES = {
    "Every claim checks out": {
        "question": "Can I return something I haven't used?",
        "answer": "Yes. Unused items can go back within 30 days of delivery for a full refund [returns-window].",
        "sources": [_RETURNS, _LABEL]},
    "One sentence is wrong": {
        "question": "Do returns cost anything?",
        "answer": "You have 30 days to return unused items [returns-window]. Return shipping is always free [returns-label].",
        "sources": [_RETURNS, _LABEL]},
    "Made-up citation": {
        "question": "Can I return opened software?",
        "answer": "Opened software can be returned within 14 days [software-policy].",
        "sources": [_RETURNS, _LABEL]},
}


class State(TypedDict, total=False):
    input: dict
    claims: list[dict]                            # split_claims + code_check, in answer order
    checks: Annotated[list[dict], operator.add]   # one per parallel jev_check
    jev: Run
    llm_judge: Run
    trust_citations: Run


def split(state: State) -> State:
    ids = {s["id"] for s in state["input"]["sources"]}
    return {"claims": [c | {"code": code_check(c, ids)} for c in split_claims(state["input"]["answer"])]}


def fan_out(state: State) -> list:
    """One Send per (claim, cited source) that code could not settle. The question is not sent: whether
    a source says a sentence does not depend on what was asked, and the claim is what gets checked."""
    by_id = {s["id"]: s for s in state["input"]["sources"]}
    sends = [Send("jev_check", {"i": i, "claim": c["text"], "source": by_id[sid]})
             for i, c in enumerate(state["claims"]) if c["code"] is None for sid in c["cites"]]
    return (sends or ["jev_verdict"]) + ["llm_judge", "trust_citations"]   # no pairs: code already decided


def jev_check(payload: dict) -> State:
    return {"checks": [jev_client.check_pair(payload["claim"], payload["source"]) | {"i": payload["i"]}]}


def _total(costs) -> float | None:
    costs = list(costs)
    return None if any(c is None for c in costs) else sum(costs)


def jev_verdict(state: State) -> State:
    cs = state.get("checks", [])
    claims = []
    for i, c in enumerate(state["claims"]):
        mine = [{"source": x["source_id"], "choice": x["choice"], "confidence": round(x["confidence"], 2)}
                for x in cs if x["i"] == i]
        claims.append(c | {"checks": mine, "verdict": "insufficient" if c["code"] else claim_verdict(mine)})
    label = answer_verdict([c["verdict"] for c in claims])
    worst = next((c for c in claims if c["verdict"] == label), None)
    return {"jev": Run(
        variant="jev", model=next((x["model"] for x in cs), settings.JEV_MODEL), label=label,
        confidence=min((x["confidence"] for x in cs), default=None),
        latency_ms=max((x["latency_ms"] for x in cs), default=0.0),   # parallel: the slowest pair, once
        input_tokens=sum(x["input_tokens"] for x in cs), output_tokens=sum(x["output_tokens"] for x in cs),
        cost_usd=_total(x["cost_usd"] for x in cs),
        raw={"claims": claims, "calls": len(cs),
             "reason": f'"{worst["text"]}" → {worst["code"] or worst["verdict"]}' if worst else "no claims"},
    )}


def llm_judge_node(state: State) -> State:
    inp = state["input"]
    label, reason, call = llm.judge(inp["question"], inp["answer"], inp["sources"])
    return {"llm_judge": Run(
        variant="llm_judge", model=call["model"], label=label, confidence=None, latency_ms=call["latency_ms"],
        input_tokens=call["input_tokens"], output_tokens=call["output_tokens"], cost_usd=call["cost_usd"],
        raw={"reason": reason, "finish_reason": call.get("finish_reason")})}


def trust_citations_node(state: State) -> State:
    """What an app does when it renders [brackets] as proof: every sentence cites something, so ship it."""
    uncited = [c["text"] for c in state["claims"] if not c["cites"]]
    return {"trust_citations": Run(
        variant="trust_citations", model="(no model)", label="insufficient" if uncited else "supported",
        confidence=None, latency_ms=0.0, input_tokens=0, output_tokens=0, cost_usd=0.0,
        raw={"reason": f'uncited: "{uncited[0]}"' if uncited else "every sentence has a citation"})}


def build_graph():
    g = StateGraph(State)
    g.add_node("split", split)
    g.add_node("jev_check", jev_check)
    g.add_node("jev_verdict", jev_verdict)
    g.add_node("llm_judge", llm_judge_node)
    g.add_node("trust_citations", trust_citations_node)
    g.add_edge(START, "split")
    g.add_conditional_edges("split", fan_out, ["jev_check", "jev_verdict", "llm_judge", "trust_citations"])
    g.add_edge("jev_check", "jev_verdict")   # once, after every parallel check is in
    for name in ("jev_verdict", "llm_judge", "trust_citations"):
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    handler = langchain_handler()
    with propagate_attributes(trace_name=TITLE, tags=["10_citation_verifier"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()
    tid = trace_id(handler)
    return Result(runs={v: out[v] for v in ("jev", "llm_judge", "trust_citations")},
                  trace_url=trace_url(tid), trace_id=tid)
