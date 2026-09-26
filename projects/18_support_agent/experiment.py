"""Project 18: customer support agent, end to end. Triage, route, look up the facts, answer, grade.
Jev triages in ONE call (intent, needs a human, urgency); code routes and escalates; a specialist answers from the
order facts. Against: one LLM agent that triages and answers in a single prompt. Every answer is graded."""

import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from config import settings
from config.telemetry import langchain_handler, langfuse, propagate_attributes, trace_id, trace_url
from core.run import Result, Run
from shared.grader import grade
from shared.openrouter import chat_model, decide_traced, metered_call

TITLE = "18 · Customer Support Agent"
PRIMITIVE = "Choice + 2 Nouls in one call → code routes → specialist answers (graded)"
POLICY = ("Refunds: unused items within 30 days, to the original payment method. Duplicate charges are always "
          "refunded. Change-of-mind returns pay a $5 label. Gift cards cannot be refunded. Acme Plus is $9/month. "
          "Express orders placed before 2pm arrive the next business day. Addresses can be changed until an order "
          "ships. Password reset links expire after 1 hour. Two-factor: Settings > Security, authenticator app.")
ROUTES = {"billing": "charges, refunds, subscriptions, gift cards", "orders": "where an order is, delivery, address",
          "tech": "app or website problems, login, account settings, email delivery"}
LABELS = [*ROUTES, "human"]
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Angry, but routine": {"message": "WHY did you charge me $9 AGAIN this month?! I never asked for this!!",
                           "facts": {"subscription": "Acme Plus, monthly, $9, renewed 2026-09-01"},
                           "rubric": "Required: explains the $9 is the Acme Plus monthly renewal."},
    "Calm, but legal": {"message": "Please note that my lawyer will contact you regarding the injury your heater caused.",
                        "facts": {"order": {"id": "6120", "item": "space heater", "status": "delivered"}}},
    "Where is my order": {"message": "Where is order 7730?",
                          "facts": {"order": {"id": "7730", "status": "out for delivery", "eta": "today"}},
                          "rubric": "Required: order 7730 is out for delivery and arrives today."},
}

TRIAGE = {
    "intent": {"type": "choice", "instructions": "Which team's job is message?", "criteria": ROUTES},
    "needs_human": {"type": "noul", "instructions": "message needs a human agent, not an automated reply",
                    "criteria": {"true": "A legal threat, an injury or safety issue, a threat to leave or go public, a "
                                         "security incident, or a request no standard tool can resolve",
                                 "false": "A routine request, however angrily or urgently it is written"}},
    "urgency": {"type": "noul", "instructions": "message needs a reply today",
                "criteria": {"true": "A deadline, an outage, or money or access blocked right now",
                             "false": "Can wait for the normal queue"}},
}
ESCALATE = 0.5


class State(TypedDict, total=False):
    input: dict
    jev: Run
    single_agent: Run


def _answer(route: str, inp: dict) -> tuple[str, dict]:
    """The specialist: the same model and cap for every variant; the facts are what its lookup tool returned."""
    msg, call = metered_call(f"agent.{route}", chat_model(None, settings.ANSWER_MAX_TOKENS), [
        SystemMessage(f"You are Acme's {route} support agent ({ROUTES[route]}). Answer the customer in 2-4 sentences "
                      f"using only the policy and the looked-up facts. Policy: {POLICY}"),
        HumanMessage(json.dumps({"message": inp["message"], "looked_up": inp.get("facts", {})}))])
    return (msg.content if isinstance(msg.content, str) else str(msg.content)), call


def _run(variant: str, route: str | None, answer: str | None, inp: dict, calls: list[dict], **raw) -> Run:
    g = grade(inp["message"], inp["rubric"], answer) if answer and inp.get("rubric") else None
    costs = [c["cost_usd"] for c in calls]
    return Run(variant=variant, model=calls[0]["model"] or settings.BASELINE_MODEL, label=route,
               confidence=raw.pop("confidence", None), latency_ms=sum(c["latency_ms"] for c in calls),
               input_tokens=sum(c["input_tokens"] for c in calls), output_tokens=sum(c["output_tokens"] for c in calls),
               cost_usd=None if any(c is None for c in costs) else sum(costs),
               quality=g["quality"] if g else None,
               raw=raw | {"answer": answer, "grade_cost": g["cost_usd"] if g else None,
                          "route": "human" if route == "human" else route})


def jev_node(state: State) -> State:
    inp = state["input"]   # the rubric never goes in: message and facts only
    a, meta = decide_traced("jev.triage", {"message": inp["message"], "facts": inp.get("facts", {})}, TRIAGE)
    intent, human, urgent = a["intent"]["choice"], float(a["needs_human"]["noul"]), float(a["urgency"]["noul"])
    route = "human" if human >= ESCALATE else intent
    answer, calls = None, [meta]
    if route != "human":
        answer, call = _answer(route, inp)
        calls.append(call)
    return {"jev": _run("jev", route, answer, inp, calls, confidence=float(a["intent"]["confidence"]),
                        needs_human=round(human, 2), priority="high" if urgent >= 0.5 else "normal",
                        reason=f"intent {intent} ({a['intent']['confidence']:.2f}), needs_human {human:.2f}, "
                               f"urgency {urgent:.2f} → {route}")}


def single_agent_node(state: State) -> State:
    """The one-prompt agent: decides the route, whether to escalate, and writes the reply, all at once."""
    inp = state["input"]
    llm = chat_model(None, settings.ANSWER_MAX_TOKENS).with_structured_output(
        {"title": "reply", "type": "object",
         "properties": {"route": {"type": "string", "enum": LABELS}, "answer": {"type": "string"}},
         "required": ["route", "answer"], "additionalProperties": False},
        method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("agent.single", llm, [
        SystemMessage("You are Acme's support agent. Pick the team (" + "; ".join(f"{k}: {v}" for k, v in ROUTES.items())
                      + "), or 'human' for legal threats, injuries or safety issues, threats to leave or go public, "
                        "security incidents, or anything no standard tool can resolve. Unless it is 'human', answer in "
                        f"2-4 sentences using only the policy and the looked-up facts. Policy: {POLICY}"),
        HumanMessage(json.dumps({"message": inp["message"], "looked_up": inp.get("facts", {})}))])
    p = out["parsed"] if isinstance(out["parsed"], dict) else {}
    route = p.get("route") if p.get("route") in LABELS else None
    answer = p.get("answer") if route not in (None, "human") else None
    return {"single_agent": _run("single_agent", route, answer, inp, [call],
                                 finish_reason=call.get("finish_reason"), reason=f"route {route}")}


NODES = {"jev": jev_node, "single_agent": single_agent_node}


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
    with propagate_attributes(trace_name=TITLE, tags=["18_support_agent"]):
        out = GRAPH.invoke({"input": inp}, config={"callbacks": [handler], "run_name": TITLE})
    langfuse().flush()
    tid = trace_id(handler)
    return Result(runs={v: out[v] for v in NODES}, trace_url=trace_url(tid), trace_id=tid)
