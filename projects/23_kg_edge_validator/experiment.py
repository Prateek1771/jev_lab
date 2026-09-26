"""Project 23: knowledge graph edge validator. An LLM extracted (subject, relation, object) from a document; may the
edge go into the graph? Code checks both entities are in the document; Jev checks the document states the relation
(direction, tense, negation). Against: storing every extracted edge, and the LLM checking its own extraction."""

import json
import re
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from config import settings
from core.run import Result, Run
from shared import openrouter
from shared.openrouter import ask_structured

TITLE = "23 · Knowledge Graph Edge Validator"
PRIMITIVE = "Choice (supports / contradicts / not_stated) + code entity check"
RELATIONS = {   # what each edge claims, in words: tense and direction are part of the meaning
    "works_at": "subject currently works at object", "founded": "subject founded object",
    "ceo_of": "subject is currently the CEO or leader of object", "coo_of": "subject is currently COO of object",
    "acquired": "subject bought object (completed, not planned)", "manages": "subject is object's manager",
    "headquartered_in": "subject's headquarters are currently in object", "owns": "subject currently owns object",
}
STORE = 0.5   # store when P(supports) is at least this; the sweep shows the tradeoff
LABELS = ["valid", "invalid"]
SWEEP = {"positive": "valid", "value": "probability"}
SAFETY = {"unsafe": "invalid", "safe": "valid", "names": ["Bad edges rejected", "Bad edges STORED", "Good edges rejected"]}
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))
_D1 = ("Priya Nair joined Northwind Labs as CTO in 2023. Before that, she spent six years at Contoso, where she led "
       "the payments team. Northwind's CEO, Tom Becker, founded the company in 2019.")
EXAMPLES = {
    "Current job": {"document": _D1, "subject": "Priya Nair", "relation": "works_at", "object": "Northwind Labs"},
    "Former job": {"document": _D1, "subject": "Priya Nair", "relation": "works_at", "object": "Contoso"},
    "Invented entity": {"document": _D1, "subject": "Priya Nair", "relation": "works_at", "object": "Microsoft"},
}
_SYSTEM = ("You extracted this relationship from the document. Check it: is it exactly what the document states, "
           "in the right direction and tense? Relation meanings: " + json.dumps(RELATIONS) + " Answer valid or invalid.")


class State(TypedDict, total=False):
    input: dict
    jev: Run
    store_all: Run
    llm_self_check: Run


def missing_entities(inp: dict) -> list[str]:
    """Code: an entity that is nowhere in the document was invented by the extractor."""
    doc = inp["document"].lower()
    return [e for e in (inp["subject"], inp["object"]) if e.lower() not in doc
            and not all(w in doc for w in re.findall(r"\w{3,}", e.lower()))]


def jev_node(state: State) -> State:
    inp = state["input"]
    missing = missing_entities(inp)
    if missing:
        return {"jev": Run(variant="jev", model="(code rule)", label="invalid", confidence=None, latency_ms=0.0,
                           input_tokens=0, output_tokens=0, cost_usd=0.0, raw={"reason": f"not in the document: {missing}"})}
    edge = {"subject": inp["subject"], "relation": inp["relation"], "object": inp["object"],
            "means": RELATIONS[inp["relation"]].replace("subject", inp["subject"]).replace("object", inp["object"])}
    body, latency = openrouter.decide({"document": inp["document"], "edge": edge}, {"support": {
        "type": "choice", "instructions": "What does document say about edge?",
        "criteria": {"supports": "document states edge's meaning, or it follows necessarily from what document "
                                 "states, in the same direction and tense",
                     "contradicts": "document states the opposite: another direction, a past fact, a refusal, "
                                    "or a different relation",
                     "not_stated": "document doesn't say it (a rumour, a plan, or nothing about it)"}}})
    a, usage = body["answers"]["support"], body.get("usage") or {}
    p = float((a.get("probabilities") or {}).get("supports", a["confidence"] if a["choice"] == "supports" else 0.0))
    ok = p >= STORE
    return {"jev": Run(
        variant="jev", model=body.get("model", settings.JEV_MODEL), label="valid" if ok else "invalid",
        confidence=float(a["confidence"]), latency_ms=latency, input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0), cost_usd=usage.get("cost"), probability=p,
        raw={"choice": a["choice"], "p_of": "supports", "means": edge["means"], "id": body.get("id"),
             "reason": f"{a['choice']}: {edge['means']}"})}


def store_all_node(state: State) -> State:
    """Extraction goes straight into the graph."""
    return {"store_all": Run(variant="store_all", model="(no model)", label="valid", confidence=None, latency_ms=0.0,
                             input_tokens=0, output_tokens=0, cost_usd=0.0, raw={"reason": "every extracted edge is stored"})}


def llm_self_check_node(state: State) -> State:
    inp = state["input"]
    run = ask_structured(_SYSTEM, json.dumps({k: inp[k] for k in ("document", "subject", "relation", "object")}), LABELS)
    run.variant = "llm_self_check"
    return {"llm_self_check": run}


NODES = {"jev": jev_node, "store_all": store_all_node, "llm_self_check": llm_self_check_node}


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
