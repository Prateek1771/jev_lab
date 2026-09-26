"""Project 02: urgency detection. One Noul question, a threshold in code, one LangGraph."""

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.run import Result, Run
from shared.openrouter import ask_structured

from . import baseline, jev_client

TITLE = "02 · Urgency Detection"
PRIMITIVE = "Noul"

# Positive phrasing on purpose: Noul returns P(this statement is true). See "Write the
# statement you want to be true" in the Phase 2 doc.
STATEMENT = "The customer message is time-sensitive: something must happen soon or harm is happening now."
CRITERIA = {
    "true": "An outage in progress, an explicit deadline, or a request for immediate action (ASAP, now, today).",
    "false": "No time pressure. Being unhappy, rude, or using the word 'urgent' in a negated way does not count.",
}
THRESHOLD = 0.5   # placeholder until you pick one with the sweep on the Dataset tab (Phase 3, §7)
SWEEP = {"positive": "urgent", "value": "probability"}   # what the sweep tunes: P(yes) against "urgent"
LABELS = ["urgent", "not_urgent"]
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Outage now": "Production is returning 500s for every customer right now.",
    "Deadline, no 'urgent'": "We go live on Monday, please confirm the API limit increase by Friday.",
    "Negated 'urgent'": "Not urgent, but could you add a dark mode at some point?",
    "Angry, no deadline": "THIS IS THE WORST APP I HAVE EVER USED.",
}

_BASELINE_SYSTEM = (
    "Decide whether this statement is true for the customer message:\n"
    f"{STATEMENT}\n"
    f"- true: {CRITERIA['true']}\n"
    f"- false: {CRITERIA['false']}\n"
    "Reply with exactly one word: yes or no."
)
# Structured variant: same statement and criteria; the enforced schema answers in labels, not yes/no.
_STRUCTURED_SYSTEM = _BASELINE_SYSTEM.replace(
    "Reply with exactly one word: yes or no.", "Answer urgent if the statement is true, not_urgent if it is false.")


class State(TypedDict, total=False):
    message: str
    jev: Run
    baseline: Run
    structured: Run


def jev_node(state: State) -> State:
    return {"jev": jev_client.ask_noul(
        {"message": state["message"]}, "urgent", STATEMENT, CRITERIA, THRESHOLD, "urgent", "not_urgent")}


def baseline_node(state: State) -> State:
    return {"baseline": baseline.ask_yes_no(_BASELINE_SYSTEM, state["message"], "urgent", "not_urgent")}


def structured_node(state: State) -> State:
    return {"structured": ask_structured(_STRUCTURED_SYSTEM, state["message"], LABELS)}


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
    out = GRAPH.invoke({"message": text})
    return Result.of(*(out[name] for name in NODES))
