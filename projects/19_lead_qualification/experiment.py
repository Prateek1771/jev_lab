"""Project 19: lead qualification. Sales now, nurture, or disqualify?
Jev: two Scores in one call (ICP fit, purchase intent); code checks company size and routes. Against: points-based
lead scoring ($0), and an LLM classifier given the same profile."""

import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from config import settings
from core.run import Result, Run
from shared import openrouter
from shared.openrouter import ask_structured

from .scoring import FIT_LEVELS, ICP, INTENT_LEVELS, JEV_ICP, points, route

TITLE = "19 · Lead Qualification"
PRIMITIVE = "2 Scores in one call (ICP fit · purchase intent) → code routes"
LABELS = ["sales_now", "nurture", "disqualify"]
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Big title, tiny company": {"company": "Two-person crypto wallet startup", "employees": 3,
                                "title": "VP of Engineering", "email": "vp@walletz.example",
                                "message": "Send me pricing and a demo link, we're evaluating this week."},
    "Buying for the boss": {"company": "Regional bank, 900 employees", "employees": 900, "title": "Procurement Manager",
                            "email": "j.ortiz@northbank.example",
                            "message": "Our CISO asked me to get a quote for fraud monitoring by Friday."},
    "Right fit, just reading": {"company": "Payments processor, 400 employees", "employees": 400,
                                "title": "Head of Fraud", "email": "m.chen@paysure.example",
                                "message": "Loved your blog post on false positives, just following along for now."},
}

QUESTIONS = {
    "icp_fit": {"type": "score", "instructions": "How well does lead match icp?", "criteria": FIT_LEVELS},
    "purchase_intent": {"type": "score", "instructions": "How strong is lead's intent to buy now?", "criteria": INTENT_LEVELS},
}
_SYSTEM = ("Qualify this sales lead against the ideal customer profile: " + json.dumps(ICP)
           + ". sales_now: strong fit, 50-2,000 employees, and actively buying (demo, trial, quote or pricing with a "
             "timeline). disqualify: not a fit or a disqualifier applies. nurture: everything else.")


class State(TypedDict, total=False):
    input: dict
    jev: Run
    points: Run
    structured: Run


def jev_node(state: State) -> State:
    lead = state["input"]
    body, latency = openrouter.decide({"icp": JEV_ICP, "lead": lead}, QUESTIONS)
    a, usage = body["answers"], body.get("usage") or {}
    fit, intent = float(a["icp_fit"]["score"]), float(a["purchase_intent"]["score"])
    label = route(fit, intent, lead["employees"])
    return {"jev": Run(
        variant="jev", model=body.get("model", settings.JEV_MODEL), label=label,
        confidence=min(float(a["icp_fit"]["confidence"]), float(a["purchase_intent"]["confidence"])),
        latency_ms=latency, input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
        cost_usd=usage.get("cost"),
        raw={"fit": round(fit, 2), "intent": round(intent, 2), "id": body.get("id"),
             "reason": f"fit {fit:.2f}, intent {intent:.2f}, {lead['employees']} employees → {label}"})}


def points_node(state: State) -> State:
    label, p = points(state["input"])
    return {"points": Run(variant="points", model="(no model)", label=label, confidence=None, latency_ms=0.0,
                          input_tokens=0, output_tokens=0, cost_usd=0.0, raw={"reason": f"{p} points → {label}"})}


def structured_node(state: State) -> State:
    return {"structured": ask_structured(_SYSTEM, json.dumps(state["input"]), LABELS)}


NODES = {"jev": jev_node, "points": points_node, "structured": structured_node}


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
