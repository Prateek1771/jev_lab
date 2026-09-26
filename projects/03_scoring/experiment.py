"""Project 03: ticket severity. One Score question on an ordered 3-level rubric, three variants, one LangGraph."""

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.run import Result, Run
from shared.openrouter import ask_plain, ask_structured

from . import jev_client

TITLE = "03 · Severity Scoring"
PRIMITIVE = "Score"

QUESTION = "How severe is the problem described in this support ticket?"
LEVELS = {   # ordered, lowest first: Score treats the list position as the scale
    "low": "Inconvenience only: cosmetic issue, a question, or a problem with an easy workaround",
    "medium": "Broken for this customer or a few users, no good workaround, but nothing lost or exposed",
    "high": "Outage, data loss, security exposure, or money at risk, for many users or for anyone's data",
}
LABELS = list(LEVELS)
SWEEP = {"positive": "high", "value": "score"}   # "escalate if score >= t", tuned against the "high" rows
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Loud but cosmetic": "THIS APP IS TERRIBLE, THE FONT IS TOO SMALL!!!",
    "Calm security exposure": "quick note, I think customer passwords are visible in the audit log export",
    "One user locked out": "Two-factor codes don't work on my new phone, so I can't log in.",
    "Outage": "Checkout is down for all our customers since 10am.",
}

_BASELINE_SYSTEM = (
    f"{QUESTION}\n"
    + "\n".join(f"- {k}: {v}" for k, v in LEVELS.items())
    + "\nReply with exactly one word: low, medium, or high."
)


class State(TypedDict, total=False):
    ticket: str
    jev: Run
    baseline: Run
    structured: Run


def jev_node(state: State) -> State:
    return {"jev": jev_client.ask_score({"ticket": state["ticket"]}, "severity", QUESTION, LEVELS)}


def baseline_node(state: State) -> State:
    return {"baseline": ask_plain(_BASELINE_SYSTEM, state["ticket"], set(LABELS))}


def structured_node(state: State) -> State:
    return {"structured": ask_structured(_BASELINE_SYSTEM, state["ticket"], LABELS)}


NODES = {"jev": jev_node, "baseline": baseline_node, "structured": structured_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(text: str) -> Result:
    out = GRAPH.invoke({"ticket": text})
    return Result.of(*(out[name] for name in NODES))
