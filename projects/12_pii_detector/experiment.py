"""Project 12: PII detector. Does this text carry a real person's personal data? If so, redact before the LLM.
Code finds PII-shaped strings (and does the redacting); Jev judges whether it is really a person's data.
Against: those regexes alone ($0), and an LLM classifier."""

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.run import Result, Run
from shared.openrouter import ask_noul, ask_structured

from . import detectors

TITLE = "12 · PII Detector"
PRIMITIVE = "Noul (+ regex spans for redaction)"

# Found in the real test: "personal data about a person" let a company's live API key through (P = 0.46).
# The readme's list includes keys and passwords, and they must not reach an LLM either, so the statement names them.
STATEMENT = "text contains a real person's personal data, or a real secret such as a password, API key or token."
CRITERIA = {
    "true": "Something that identifies or exposes a real person: their email, phone, home address, ID or card "
            "number, date of birth, health or money details; or a working password, key or token, whoever owns it; "
            "in any wording or format.",
    "false": "Company or support contact details, documentation placeholders and test values (example.com, test "
             "cards, EXAMPLE keys), order or ticket numbers, public figures' public roles, aggregate statistics, "
             "or a format being explained.",
}
THRESHOLD = 0.5
SWEEP = {"positive": "pii", "value": "probability"}
LABELS = ["pii", "clean"]
SAFETY = {"unsafe": "pii", "safe": "clean", "names": ["PII caught", "PII MISSED", "Clean text flagged"]}
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Email and phone": "Hi, it's Priya Nair, reach me at priya.nair@gmail.com or +44 7700 900123 about my refund.",
    "No regex can see it": "My neighbour Tom Becker at 14 Elm Street was just diagnosed with diabetes, can you "
                           "recommend a meal kit for him?",
    "Looks like PII, isn't": "Use the test card 4242 4242 4242 4242 in sandbox mode, and email support@acme.test "
                             "if order #5550123456 fails.",
}

_SYSTEM = (
    f"Decide whether this statement is true for the text:\n{STATEMENT}\n"
    f"- true: {CRITERIA['true']}\n- false: {CRITERIA['false']}\n"
    "Answer pii if the statement is true, clean if it is false."
)


class State(TypedDict, total=False):
    text: str
    hits: list[dict]
    jev: Run
    regex: Run
    structured: Run


def _redaction(text: str, hits: list[dict]) -> dict:
    return {"found": [f"{h['kind']}: {h['value']}" for h in hits], "redacted": detectors.redact(text, hits)}


def jev_node(state: State) -> State:
    run = ask_noul({"text": state["text"]}, "pii", STATEMENT, CRITERIA, THRESHOLD, "pii", "clean")
    hits = detectors.find(state["text"])
    if run.label == "pii":   # what the LLM would receive: regex spans masked; anything else needs a human
        run.raw |= _redaction(state["text"], hits) | (
            {} if hits else {"reason": "PII with no regex shape: redact by hand or refuse"})
    return {"jev": run}


def regex_node(state: State) -> State:
    hits = detectors.find(state["text"])
    return {"regex": Run(
        variant="regex", model="(no model)", label="pii" if hits else "clean", confidence=None, latency_ms=0.0,
        input_tokens=0, output_tokens=0, cost_usd=0.0,
        raw=_redaction(state["text"], hits) | {"reason": ", ".join(sorted({h["kind"] for h in hits})) or "no match"})}


def structured_node(state: State) -> State:
    return {"structured": ask_structured(_SYSTEM, state["text"], LABELS)}


NODES = {"jev": jev_node, "regex": regex_node, "structured": structured_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(text: str) -> Result:
    out = GRAPH.invoke({"text": text})
    return Result.of(*(out[name] for name in NODES))
