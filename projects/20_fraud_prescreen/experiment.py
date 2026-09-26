"""Project 20: fraud pre-screening on synthetic transactions. Allow, review, or investigate?
Code computes the facts; Jev scores the risk. The ladder spends frontier reasoning only where Jev sees risk.
Against: a rules engine ($0), and the frontier model on every transaction."""

import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run
from shared.openrouter import chat_model, decide_traced, metered_call

from .features import features, rules

TITLE = "20 · Fraud Pre-screening"
PRIMITIVE = "Score (risk) → bands; frontier only above low (the ladder)"
LABELS = ["allow", "review", "investigate"]
# Jev's risk score 0..2: below LOW allow, from HIGH investigate, between review. The first real run used
# placeholders (0.6, 1.4): a $4.50 coffee scored 0.93 and went to review, and the ladder sent 90% of traffic to the
# frontier. Stored scores: normal customers <= 0.93, review cases 0.95-1.54, fraud >= 1.68. These are the midpoints
# between those classes, i.e. tuned on the same 21 rows: optimistic until checked on new traffic.
LOW, HIGH = 0.94, 1.6
SWEEP = {"positive": "investigate", "value": "score"}   # re-tune HIGH from any dataset run, no API calls
SAFETY = {"unsafe": "investigate", "safe": "allow",
          "names": ["Fraud sent to investigation", "Fraud ALLOWED", "Good customers stopped"]}
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Card testing": {"amount": 1.0, "usual_amount": 60, "merchant": "online donation page", "country": "US",
                     "home_country": "US", "device": "new", "tx_last_hour": 7},
    "Big but normal": {"amount": 2400, "usual_amount": 180, "merchant": "electronics store, customer's home city",
                       "country": "UK", "home_country": "UK", "device": "known",
                       "note": "customer browsed this laptop in the store's app for three days"},
    "Takeover pattern": {"amount": 450, "usual_amount": 70, "merchant": "gift cards, online", "country": "UK",
                         "home_country": "UK", "device": "new", "shipping_changed_today": True},
}
RISK = {"risk": {"type": "score", "instructions": "How likely is transaction to be fraud, given facts?",
                 "criteria": ["Low: consistent with this customer's normal behaviour",
                              "Medium: unusual in one way, plausibly innocent",
                              "High: matches a fraud pattern (card testing, account takeover, cash-out)"]}}
_FRONTIER = ("You are a senior fraud analyst. Decide what happens to this card transaction: allow (normal for the "
             "customer), review (unusual, needs a quick check), or investigate (matches a fraud pattern).")


class State(TypedDict, total=False):
    input: dict
    jev: Run
    ladder: Run
    rules_engine: Run
    frontier_all: Run


def _state(tx: dict) -> dict:
    return {"transaction": tx, "facts": features(tx)}


def _frontier(tx: dict) -> tuple[str | None, dict]:
    llm = chat_model(settings.MODEL_TIERS["frontier"], settings.AGENT_MAX_TOKENS).with_structured_output(
        {"title": "decision", "type": "object", "properties": {"decision": {"type": "string", "enum": LABELS}},
         "required": ["decision"], "additionalProperties": False}, method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("frontier.decide", llm, [SystemMessage(_FRONTIER), HumanMessage(json.dumps(_state(tx)))])
    d = out["parsed"].get("decision") if isinstance(out["parsed"], dict) else None
    return (d if d in LABELS else None), call


def _band(score: float) -> str:
    return "allow" if score < LOW else "investigate" if score >= HIGH else "review"


def _run(variant: str, label: str | None, calls: list[dict], **raw) -> Run:
    costs = [c["cost_usd"] for c in calls]
    return Run(variant=variant, model=next((c["model"] for c in reversed(calls) if c["model"]), "(no model)"),
               label=label, confidence=raw.pop("confidence", None), latency_ms=sum(c["latency_ms"] for c in calls),
               input_tokens=sum(c["input_tokens"] for c in calls), output_tokens=sum(c["output_tokens"] for c in calls),
               cost_usd=None if any(c is None for c in costs) else sum(costs), score=raw.pop("score", None), raw=raw)


def _jev(tx: dict) -> tuple[float, float, dict]:
    a, meta = decide_traced("jev.risk", _state(tx), RISK)
    return float(a["risk"]["score"]), float(a["risk"]["confidence"]), meta


def jev_node(state: State) -> State:
    s, conf, meta = _jev(state["input"])
    return {"jev": _run("jev", _band(s), [meta], score=s, confidence=conf, levels=3,
                        reason=f"risk {s:.2f} → {_band(s)}")}


def ladder_node(state: State) -> State:
    """The readme's cost ladder: Jev screens everything; only non-low risk reaches the frontier model."""
    tx = state["input"]
    s, conf, meta = _jev(tx)
    if _band(s) == "allow":
        return {"ladder": _run("ladder", "allow", [meta], score=s, levels=3, frontier=0.0,
                               reason=f"risk {s:.2f}: allowed without the frontier")}
    d, call = _frontier(tx)
    return {"ladder": _run("ladder", d, [meta, call], score=s, levels=3, frontier=1.0,
                           reason=f"risk {s:.2f} → frontier: {d}")}


def rules_engine_node(state: State) -> State:
    label, why = rules(state["input"])
    zero = {"model": None, "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    return {"rules_engine": _run("rules_engine", label, [zero], reason=why)}


def frontier_all_node(state: State) -> State:
    d, call = _frontier(state["input"])
    return {"frontier_all": _run("frontier_all", d, [call], frontier=1.0, reason=f"frontier: {d}")}


NODES = {"jev": jev_node, "ladder": ladder_node, "rules_engine": rules_engine_node, "frontier_all": frontier_all_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict) -> Result:
    handler = langchain_handler()
    with propagate_attributes(trace_name=TITLE, tags=["20_fraud_prescreen"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()
    tid = trace_id(handler)
    return Result(runs={v: out[v] for v in NODES}, trace_url=trace_url(tid), trace_id=tid)
