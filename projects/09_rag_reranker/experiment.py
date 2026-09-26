"""Project 09: RAG reranker. Retrieve 10 chunks, put them in order, give the answer the top 3, grade it.
Jev scores each chunk on its own, in parallel; an LLM ranks all 10 in one prompt; or keep the retriever's order."""

import json
import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run
from shared.grader import grade

from . import jev_client, llm, ranking
from .retriever import retrieve

TITLE = "09 · RAG Reranker"
PRIMITIVE = "Score per chunk (parallel calls) · Noul (grade)"
LABELS = ["answer", "no_answer"]
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Buried answer": {"question": "How long do I have to return an item?",
                      "rubric": "Required: 30 days from delivery.",
                      "gold": {"returns-window": 2, "returns-how": 1, "returns-label-cost": 1, "returns-faq": 1}},
    "Overview page on top": {"question": "Which payment methods do you accept?",
                             "rubric": "Required: Visa, Mastercard, American Express, PayPal and Apple Pay.",
                             "gold": {"pay-methods": 2, "payments-overview": 1}},
    "Not in the help centre": {"question": "Is there a student discount?",
                               "rubric": "Required: the reply is NO_ANSWER, or says the help centre does not mention one. Must not: invent a discount.",
                               "gold": {}},
}


class State(TypedDict, total=False):
    input: dict
    chunks: list[dict]
    scores: Annotated[list[dict], operator.add]   # one per parallel jev_score
    jev: Run
    llm_rank: Run
    retriever_order: Run


def _question(state) -> str:
    return state["input"]["question"]   # the only field any ranker or answerer sees; gold and rubric never


def retrieve_node(state: State) -> State:
    return {"chunks": retrieve(_question(state), settings.RERANK_N)}


def fan_out(state: State) -> list:
    return [Send("jev_score", {"question": _question(state), "chunk": c}) for c in state["chunks"]] + \
        ["llm_rank", "retriever_order"]


def jev_score(payload: dict) -> State:
    return {"scores": [jev_client.score_chunk(payload["question"], payload["chunk"])]}


def _total(costs) -> float | None:
    costs = list(costs)
    return None if any(c is None for c in costs) else sum(costs)


def _answered(variant: str, state: State, order: list[str], calls: list[dict], raw=None) -> Run:
    """Answer from the top K of `order`, grade it, and score the ORDER against the gold grades."""
    inp, by_id = state["input"], {c["id"]: c for c in state["chunks"]}
    top = order[:settings.RERANK_K]
    text, call = llm.answer(_question(state), [by_id[i] for i in top])
    calls = calls + [call]
    g = grade(inp["question"], inp["rubric"], text)
    gold = inp.get("gold", {})
    return Run(
        variant=variant, model=settings.BASELINE_MODEL,
        label="no_answer" if text.strip().startswith(llm.NO_ANSWER) else "answer",
        confidence=None,
        latency_ms=sum(c["latency_ms"] for c in calls),
        input_tokens=sum(c["input_tokens"] for c in calls), output_tokens=sum(c["output_tokens"] for c in calls),
        cost_usd=_total(c["cost_usd"] for c in calls), quality=g["quality"],
        raw=(raw or {}) | {"answer": text, "finish_reason": call.get("finish_reason"), "order": order, "top": top,
                           "ndcg": ranking.ndcg_at_k(order, gold, settings.RERANK_K), "mrr": ranking.mrr(order, gold),
                           "grade_cost": g["cost_usd"], "reason": f"top {len(top)}: {', '.join(top)}"},
    )


def jev_answer(state: State) -> State:
    ss = state["scores"]
    order = ranking.jev_order(ss, [c["id"] for c in state["chunks"]])
    calls = [{k: s[k] for k in ("latency_ms", "input_tokens", "output_tokens", "cost_usd")} for s in ss]
    run = _answered("jev", state, order, calls,
                    raw={"scores": {s["id"]: {"score": round(s["score"], 2), "p_top": round(s["p_top"], 2)} for s in ss}})
    # the scores ran in parallel: count their wall time once (the slowest), not their sum
    run.latency_ms -= sum(c["latency_ms"] for c in calls) - max((c["latency_ms"] for c in calls), default=0)
    run.model = next((s["model"] for s in ss), settings.JEV_MODEL)
    run.confidence = min((s["confidence"] for s in ss if s["id"] in run.raw["top"]), default=None)
    return {"jev": run}


def llm_rank_node(state: State) -> State:
    order, call = llm.rank(_question(state), state["chunks"])
    return {"llm_rank": _answered("llm_rank", state, order, [call])}


def retriever_order_node(state: State) -> State:
    return {"retriever_order": _answered("retriever_order", state, [c["id"] for c in state["chunks"]], [])}


def build_graph():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve_node)
    g.add_node("jev_score", jev_score)
    g.add_node("jev_answer", jev_answer)
    g.add_node("llm_rank", llm_rank_node)
    g.add_node("retriever_order", retriever_order_node)
    g.add_edge(START, "retrieve")
    g.add_conditional_edges("retrieve", fan_out, ["jev_score", "llm_rank", "retriever_order"])
    g.add_edge("jev_score", "jev_answer")   # once, after every parallel score is in
    for name in ("jev_answer", "llm_rank", "retriever_order"):
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    handler = langchain_handler()
    with propagate_attributes(trace_name=TITLE, tags=["09_rag_reranker"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()
    tid = trace_id(handler)
    return Result(runs={v: out[v] for v in ("jev", "llm_rank", "retriever_order")},
                  trace_url=trace_url(tid), trace_id=tid)
