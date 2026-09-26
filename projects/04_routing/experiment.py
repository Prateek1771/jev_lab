"""Project 04: action routing. Jev answers three questions; code decides; the graph acts.
The action nodes are reachable only through the edge for their decision."""

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.run import Result, Run
from shared.openrouter import ask_plain, ask_structured

from . import jev_client, policy

TITLE = "04 · Action Routing"
PRIMITIVE = "Choice + Noul + Score (one call)"
LABELS = policy.DECISIONS
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

REFUND_POLICY = (
    "Duplicate charges and orders that never arrived are eligible for a refund. Change-of-mind returns are "
    "eligible only within 30 days of delivery and only for unused items. Anything else is not eligible."
)
RETURN_WINDOW_DAYS = 30
INTENTS = {
    "refund": "Wants money back or a credit",
    "status": "Asking where an order, ticket, or earlier refund is",
    "bug": "Reporting something broken in the product",
    "how_to": "Needs help using the product",
    "other": "Anything else",
}
QUEUES = {"refund": "queue.billing", "status": "queue.orders", "bug": "queue.engineering",
          "how_to": "queue.support", "other": "queue.general"}

EXAMPLES = {
    "Duplicate charge": {"message": "I was charged twice for order A-104. Please refund the duplicate.",
                         "order": "A-104: two captured charges of $49", "prior_refunds_30d": 0, "days_since_delivery": 2},
    "Angry, about to leave": {"message": "Charged twice AGAIN. Refund it today or I'm cancelling my account.",
                              "order": "A-201: two captured charges of $19", "prior_refunds_30d": 0,
                              "days_since_delivery": 1},
    "Outside return window": {"message": "Changed my mind about the lamp, it's unused. Refund please.",
                              "order": "L-88: desk lamp, delivered", "prior_refunds_30d": 0, "days_since_delivery": 45},
    "Unclear": {"message": "You know what I mean. Just fix it.", "order": None, "prior_refunds_30d": 0,
                "days_since_delivery": None},
}


def facts_from(inp: dict) -> dict:
    """Counting and date comparison run in code, not in Jev (TypeSafe's jaggedness note for jev-1.13)."""
    days = inp.get("days_since_delivery")
    return {
        "has_order": bool(inp.get("order")),
        "prior_refunds_30d": int(inp.get("prior_refunds_30d") or 0),
        "within_return_window": days is not None and days <= RETURN_WINDOW_DAYS,
    }


def llm_view(inp: dict, facts: dict) -> str:
    """What both LLM baselines see: the same facts Jev and the policy get, as JSON."""
    return json.dumps({"message": inp["message"], "order": inp.get("order"), "refund_policy": REFUND_POLICY,
                       "within_return_window": facts["within_return_window"],
                       "prior_refunds_30d": facts["prior_refunds_30d"]})


_BASELINE_SYSTEM = (
    "You route customer support tickets. Choose exactly one action:\n"
    "- human: you cannot tell what the customer wants.\n"
    "- route_queue: they want something other than a refund (order status, a bug, how-to, anything else).\n"
    "- block: they want a refund that refund_policy does not support.\n"
    "- refund_auto: a refund the policy clearly supports, with an order on file, fewer than 2 refunds in the "
    "last 30 days, and no sign the customer is about to leave.\n"
    "- refund_confirm: any other refund request the policy supports.\n"
    "Reply with exactly one action name and nothing else."
)


class State(TypedDict, total=False):
    input: dict
    facts: dict
    answers: dict
    decision: str
    reason: str
    jev: Run
    baseline: Run
    structured: Run


# --- the Jev path: ask -> decide -> (conditional edge) -> act -----------------------------

def jev_ask(state: State) -> State:
    inp = state["input"]
    facts = facts_from(inp)
    jev_state = {"message": inp["message"], "order": inp.get("order"), "refund_policy": REFUND_POLICY,
                 "within_return_window": facts["within_return_window"]}   # only what the questions need
    a = jev_client.ask_ticket(jev_state, INTENTS)
    decision, reason = policy.choose(a["intent"], a["intent_conf"], a["policy_ok"], a["churn"], facts)
    return {"facts": facts, "answers": a, "decision": decision, "reason": reason}


def _jev_run(state: State, actions: list[str]) -> State:
    a = state["answers"]
    return {"jev": Run(
        variant="jev", model=a["model"], label=state["decision"], confidence=a["intent_conf"],
        latency_ms=a["latency_ms"], input_tokens=a["input_tokens"], output_tokens=a["output_tokens"],
        cost_usd=a["cost_usd"],
        raw={"band": policy.BANDS[state["decision"]], "reason": state["reason"], "actions": actions,
             "answers": {k: a[k] for k in ("intent", "intent_conf", "policy_ok", "churn")},
             "facts": state["facts"], "id": a["id"]},
    )}


# Each action string is written in exactly one node, and each node is reachable only through the edge
# named after its decision. "start_refund_flow:auto" cannot appear in a run whose decision isn't refund_auto.
def refund_auto(state: State) -> State:
    return _jev_run(state, ["start_refund_flow:auto", "route:queue.billing"])


def refund_confirm(state: State) -> State:
    return _jev_run(state, ["start_refund_flow:confirm", "route:queue.billing"])


def block(state: State) -> State:
    return _jev_run(state, ["reply:refund_policy", "route:queue.billing"])


def route_queue(state: State) -> State:
    return _jev_run(state, [f"route:{QUEUES[state['answers']['intent']]}"])


def human(state: State) -> State:
    return _jev_run(state, ["escalate:human_agent"])


ACT = {"refund_auto": refund_auto, "refund_confirm": refund_confirm, "block": block,
       "route_queue": route_queue, "human": human}


# --- the two LLM baselines decide the action themselves ----------------------------------

def baseline_node(state: State) -> State:
    return {"baseline": ask_plain(_BASELINE_SYSTEM, llm_view(state["input"], facts_from(state["input"])),
                                            set(LABELS))}


def structured_node(state: State) -> State:
    return {"structured": ask_structured(_BASELINE_SYSTEM, llm_view(state["input"], facts_from(state["input"])),
                                         LABELS)}


def build_graph():
    g = StateGraph(State)
    g.add_node("jev_ask", jev_ask)
    for name, fn in ACT.items():
        g.add_node(name, fn)
        g.add_edge(name, END)
    g.add_edge(START, "jev_ask")
    g.add_conditional_edges("jev_ask", lambda s: s["decision"], {name: name for name in ACT})
    for name, fn in (("baseline", baseline_node), ("structured", structured_node)):
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    out = GRAPH.invoke({"input": inp})
    return Result.of(out["jev"], out["baseline"], out["structured"])
