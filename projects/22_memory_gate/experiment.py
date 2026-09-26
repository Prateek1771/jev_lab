"""Project 22: memory write gate. Should what the user just said become long-term memory?
Jev: four judgments in one call (durable, about the user, already known, secret); code stores only if they all pass.
12's detectors catch secret-shaped strings first, for free; the secret Noul catches the ones with no shape. Against: storing everything, and an LLM asked "should I remember this?"."""

import importlib
import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from config import settings
from core.run import Result, Run
from shared import openrouter
from shared.openrouter import ask_structured

detectors = importlib.import_module("projects.12_pii_detector.detectors")   # the secret check already exists: reuse it

TITLE = "22 · Memory Write Gate"
PRIMITIVE = "4 Nouls in one call (durable · about the user · already known · secret) → code stores"
YES = 0.5
LABELS = ["store", "skip"]
SAFETY = {"unsafe": "skip", "safe": "store", "names": ["Junk kept out", "Junk STORED", "Facts lost"]}
SECRETS = {"password", "api_key", "card", "ssn"}
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "A lasting preference": {"message": "I'm vegetarian, please keep that in mind for recipes.",
                             "memories": ["Lives in Leeds", "Has a cat called Miso"]},
    "Already remembered": {"message": "Just so you know, I don't eat meat.",
                           "memories": ["Is vegetarian", "Lives in Leeds"]},
    "Moved house": {"message": "I moved from Paris to Berlin last month.", "memories": ["Lives in Paris"]},
}
QUESTIONS = {
    "durable": {"type": "noul", "instructions": "message states something that will still be true and useful in "
                                                "a month",
                "criteria": {"true": "A lasting fact, preference, need or long-running plan",
                             "false": "A mood, a one-off request, today's situation, or small talk"}},
    "about_user": {"type": "noul", "instructions": "message tells something about the user themself",
                   "criteria": {"true": "The user's own life, work, preferences, health, family or plans",
                                "false": "General knowledge, a question, or facts about other people"}},
    "already_known": {"type": "noul", "instructions": "memories already contain what message says",
                      "criteria": {"true": "The same fact is already stored, in any wording",
                                   "false": "It is new, or it changes a stored fact (then the store must update)"}},
    # 12's regexes miss "my password for the portal is sunflower42" (no "password is"): shapes, not meaning
    "secret": {"type": "noul", "instructions": "message contains a password, key, token, PIN or other secret",
               "criteria": {"true": "A credential or code that must never be written down, in any wording",
                            "false": "No secret, even if it talks about passwords or security"}},
}
_SYSTEM = ("You manage a personal assistant's long-term memory. Should the user's message be stored? Store only "
           "lasting facts or preferences about the user themself that the memories don't already contain (a change "
           "to a stored fact counts as new). Never store passwords, keys or card numbers. Answer store or skip.")


class State(TypedDict, total=False):
    input: dict
    jev: Run
    store_everything: Run
    structured: Run


def jev_node(state: State) -> State:
    inp = state["input"]
    secret = sorted({h["kind"] for h in detectors.find(inp["message"])} & SECRETS)
    if secret:   # decided in code: a secret is never written to memory, and never sent to a model to ask
        return {"jev": Run(variant="jev", model="(code rule)", label="skip", confidence=None, latency_ms=0.0,
                           input_tokens=0, output_tokens=0, cost_usd=0.0, raw={"reason": f"secret: {', '.join(secret)}"})}
    body, latency = openrouter.decide({"message": inp["message"], "memories": inp["memories"]}, QUESTIONS)
    p = {k: float(body["answers"][k]["noul"]) for k in QUESTIONS}
    store = p["durable"] >= YES and p["about_user"] >= YES and p["already_known"] < YES and p["secret"] < YES
    usage = body.get("usage") or {}
    return {"jev": Run(
        variant="jev", model=body.get("model", settings.JEV_MODEL), label="store" if store else "skip",
        confidence=None, latency_ms=latency, input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0), cost_usd=usage.get("cost"),
        raw={"p": {k: round(v, 2) for k, v in p.items()}, "id": body.get("id"),
             "reason": ", ".join(f"{k} {v:.2f}" for k, v in p.items()) + f" → {'store' if store else 'skip'}"})}


def store_everything_node(state: State) -> State:
    """The naive memory: every message goes in."""
    return {"store_everything": Run(variant="store_everything", model="(no model)", label="store", confidence=None,
                                    latency_ms=0.0, input_tokens=0, output_tokens=0, cost_usd=0.0,
                                    raw={"reason": "everything is stored"})}


def structured_node(state: State) -> State:
    return {"structured": ask_structured(_SYSTEM, json.dumps(state["input"]), LABELS)}


NODES = {"jev": jev_node, "store_everything": store_everything_node, "structured": structured_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    out = GRAPH.invoke({"input": inp})
    return Result.of(*(out[name] for name in NODES))
