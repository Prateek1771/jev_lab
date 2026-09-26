"""Project 01: support ticket classification. One Choice question, five labels, one LangGraph."""

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.run import Result, Run
from shared.openrouter import ask_plain, ask_structured

from . import jev_client

TITLE = "01 · Ticket Classification"
PRIMITIVE = "Choice"

QUESTION = "Which team should handle this support ticket?"
CRITERIA = {
    "billing": "Charges, invoices, refunds, payments",
    "technical": "Bugs, outages, integrations, errors",
    "account": "Login, password, permissions, profile, security settings",
    "sales": "Pricing questions, upgrades, new accounts, demos",
    "other": "Does not fit any other team",
}
LABELS = list(CRITERIA)
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Double charge": "I was charged twice for order A-104. Please refund the duplicate.",
    "Login loop": "Every time I log in it sends me back to the login page. Chrome, cleared cookies.",
    "Upgrade question": "How much would it cost to move our 40-seat team to the Enterprise plan?",
    "Ambiguous": "Your billing page throws a 500 error when I try to download my invoice.",
}

_BASELINE_SYSTEM = (
    f"{QUESTION}\n"
    + "\n".join(f"- {k}: {v}" for k, v in CRITERIA.items())
    + "\nReply with exactly one label from the list and nothing else."
)


class State(TypedDict, total=False):
    ticket: str
    jev: Run
    baseline: Run
    structured: Run


def jev_node(state: State) -> State:
    return {"jev": jev_client.ask_choice({"ticket": state["ticket"]}, "team", QUESTION, CRITERIA)}


def baseline_node(state: State) -> State:
    return {"baseline": ask_plain(_BASELINE_SYSTEM, state["ticket"], set(CRITERIA))}


def structured_node(state: State) -> State:
    # Same prompt as the plain baseline: the only difference is the enforced response format.
    return {"structured": ask_structured(_BASELINE_SYSTEM, state["ticket"], LABELS)}


NODES = {"jev": jev_node, "baseline": baseline_node, "structured": structured_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():   # fan out: every variant runs in parallel,
        g.add_node(name, fn)         # writes only its own state key, and times only its own call
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(text: str) -> Result:
    out = GRAPH.invoke({"ticket": text})
    return Result.of(*(out[name] for name in NODES))
