"""Project 05: model routing. Jev judges the task, code picks the tier, that tier's model answers,
and Jev grades every answer the same way. The question is quality per dollar, not label accuracy."""

import json
import time
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from config import settings
from core.run import Result, Run
from shared.grader import grade
from shared.openrouter import ask_structured, chat_model

from . import jev_client, router

TITLE = "05 · Model Router"
PRIMITIVE = "Score + Noul (route) · Noul (grade)"
LABELS = router.TIERS
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Easy": {"task": "Rewrite this sentence in the passive voice: 'The committee approved the budget.'",
             "rubric": "Required: a passive-voice sentence with the same meaning, e.g. 'The budget was approved by the committee.'"},
    "Looks easy, high stakes": {
        "task": "Is it fine to store our EU customers' full card numbers in our own Postgres database so "
                "repeat checkout is faster? Yes or no, and why.",
        "rubric": "Required: no, not without full PCI DSS compliance, and it names PCI DSS. Must not: say yes without that caveat."},
    "Short but hard": {
        "task": "Design a zero-downtime JWT signing key rotation for 40 services that verify tokens.",
        "rubric": "Required: publish the new key (e.g. via JWKS) before signing with it; verifiers accept old and new keys, selected by kid; retire the old key only after the longest token lifetime. Must not: switch keys in one step."},
}

ANSWER_SYSTEM = "Answer the task directly and completely. Be concise: at most about 150 words."

_ROUTER_SYSTEM = (
    "Pick the cheapest model tier that will answer this task well:\n"
    "- fast: lookups, rewrites, one-step answers.\n"
    "- balanced: several steps or some domain knowledge.\n"
    "- frontier: deep reasoning, expert knowledge, subtle trade-offs, or anything where a wrong answer "
    "could cost money, security, legal trouble, health, or data.\n"
    "Reply with the tier only."
)


class State(TypedDict, total=False):
    input: dict
    jev: Run
    llm_router: Run
    frontier: Run


def _total(*costs: float | None) -> float | None:
    """A variant's cost is None if any of its calls didn't report one: a partial sum would look cheaper."""
    return None if any(c is None for c in costs) else sum(costs)


def answer(tier: str, task: str) -> dict:
    """The task alone goes to the answering model. The rubric never does: it would leak the answer key."""
    t0 = time.perf_counter()
    msg = chat_model(settings.MODEL_TIERS[tier], settings.ANSWER_MAX_TOKENS, settings.TIER_REASONING.get(tier)).invoke(
        [SystemMessage(ANSWER_SYSTEM), HumanMessage(task)])
    usage, meta = msg.usage_metadata or {}, msg.response_metadata or {}
    return {"text": msg.content if isinstance(msg.content, str) else str(msg.content),
            "model": meta.get("model_name", settings.MODEL_TIERS[tier]),
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": meta.get("cost"), "finish_reason": meta.get("finish_reason")}


def _answered(variant: str, tier: str, route: dict | None, inp: dict, confidence=None, raw=None) -> Run:
    """Answer with `tier`, grade it, and account for it. Routing + answering is the variant's cost and
    latency; grading is measurement overhead, the same for everyone, kept apart in raw."""
    ans = answer(tier, inp["task"])
    g = grade(inp["task"], inp["rubric"], ans["text"])
    route = route or {"latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    return Run(
        variant=variant, model=ans["model"], label=tier, confidence=confidence,
        latency_ms=route["latency_ms"] + ans["latency_ms"],
        input_tokens=route["input_tokens"] + ans["input_tokens"],
        output_tokens=route["output_tokens"] + ans["output_tokens"],
        cost_usd=_total(route["cost_usd"], ans["cost_usd"]),
        quality=g["quality"],
        raw=(raw or {}) | {"answer": ans["text"], "finish_reason": ans["finish_reason"],
                           "route_cost": route["cost_usd"], "answer_cost": ans["cost_usd"],
                           "grade_cost": g["cost_usd"], "grade_id": g["id"]},
    )


def jev_node(state: State) -> State:
    a = jev_client.ask_route(state["input"]["task"])
    tier, reason = router.tier_for(a["difficulty"], a["difficulty_conf"], a["high_risk"])
    return {"jev": _answered("jev", tier, a, state["input"], confidence=a["difficulty_conf"], raw={
        "reason": reason, "router": a["model"], "route_id": a["id"],
        "answers": {k: a[k] for k in ("difficulty", "difficulty_conf", "high_risk")}})}


def llm_router_node(state: State) -> State:
    pick = ask_structured(_ROUTER_SYSTEM, state["input"]["task"], router.TIERS)
    tier = pick.label or "frontier"   # an answer outside the schema routes up, like Jev's unsure rule
    route = {"latency_ms": pick.latency_ms, "input_tokens": pick.input_tokens,
             "output_tokens": pick.output_tokens, "cost_usd": pick.cost_usd}
    return {"llm_router": _answered("llm_router", tier, route, state["input"], raw={
        "reason": f"{pick.model} picked {pick.label or 'nothing valid, so frontier'}", "router": pick.model})}


def frontier_node(state: State) -> State:
    return {"frontier": _answered("frontier", "frontier", None, state["input"], raw={"reason": "always frontier"})}


NODES = {"jev": jev_node, "llm_router": llm_router_node, "frontier": frontier_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():   # three independent paths, run in parallel, each writes its own key
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    out = GRAPH.invoke({"input": inp})
    return Result.of(*(out[name] for name in NODES))
