"""Project 15: semantic code linter. Does this change break one of the team's four rules?
Jev: one Noul per rule, all four in one call (same code, different judgments). Against: pattern-based static checks
($0), and an LLM reviewer listing the rules it thinks are broken. Scored per rule against gold violations."""

import json
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from config import settings
from core.run import Result, Run
from shared import openrouter
from shared.openrouter import chat_model, metered_call

from .rules import RULES, precision_recall, static_checks

TITLE = "15 · Semantic Code Linter"
PRIMITIVE = "4 Nouls in one call (one per team rule)"
THRESHOLD = 0.5
LABELS = ["flag", "clean"]
SAFETY = {"unsafe": "flag", "safe": "clean",
          "names": ["Bad changes flagged", "Bad changes PASSED", "Clean changes flagged"]}
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))

EXAMPLES = {
    "Debug flag skips auth": {
        "path": "routes/orders.py", "gold": ["auth_bypass"],
        "code": "@app.get('/orders/<id>')\n@require_auth\ndef get_order(id):\n    if request.args.get('debug') == '1':\n"
                "        return order_repo.get_unchecked(id)\n    return order_repo.get_for_user(id, current_user)"},
    "Masked token, looks bad": {
        "path": "services/billing.py", "gold": [],
        "code": "def charge(card_token, amount):\n    log.info(f'charging {amount} with token {card_token[:4]}****')\n"
                "    return gateway.charge(card_token, amount)"},
    "Query in a route": {
        "path": "routes/users.py", "gold": ["layering", "sensitive_exposure"],
        "code": "@app.get('/users/<id>')\n@require_auth\ndef get_user(id):\n    user = db.session.query(User).get(id)\n"
                "    return jsonify(user.to_dict())  # includes email and password_hash"},
}

_SYSTEM = ("Review this code change against the team's rules and list every rule it breaks (none if clean):\n"
           + "\n".join(f"- {k}: {r['instructions']}. Breaks it: {r['criteria']['true']}. Does not: {r['criteria']['false']}."
                       for k, r in RULES.items()))


class State(TypedDict, total=False):
    input: dict
    jev: Run
    static_checks: Run
    llm_reviewer: Run


def _scored(variant: str, model: str, flagged: list[str], gold: list[str], call: dict, **raw) -> Run:
    p, r = precision_recall(flagged, gold)
    return Run(variant=variant, model=model, label="flag" if flagged else "clean", confidence=None,
               latency_ms=call["latency_ms"], input_tokens=call["input_tokens"], output_tokens=call["output_tokens"],
               cost_usd=call["cost_usd"],
               raw=raw | {"violations": flagged, "rule_precision": p, "rule_recall": r,
                          "reason": ", ".join(flagged) or "no rule broken"})


def jev_node(state: State) -> State:
    inp = state["input"]   # gold never goes in: only path and code
    body, latency = openrouter.decide({"path": inp["path"], "code": inp["code"]},
                                      {k: {"type": "noul", **r} for k, r in RULES.items()})
    p = {k: float(body["answers"][k]["noul"]) for k in RULES}
    usage = body.get("usage") or {}
    call = {"latency_ms": latency, "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0), "cost_usd": usage.get("cost")}
    run = _scored("jev", body.get("model", settings.JEV_MODEL), [k for k in RULES if p[k] >= THRESHOLD],
                  inp.get("gold", []), call, rules={k: round(v, 2) for k, v in p.items()})
    run.probability = max(p.values())
    run.raw["p_of"] = "worst rule"   # the bar is the highest rule, not a yes/no (re-test, Puppeteer)
    top = max(p, key=p.get)   # on the page: how close each call was, not just which rules tripped
    run.raw["reason"] = (", ".join(f"{k} {p[k]:.2f}" for k in run.raw["violations"])
                         or f"no rule broken (highest: {top} {p[top]:.2f})")
    return {"jev": run}


def static_checks_node(state: State) -> State:
    inp = state["input"]
    zero = {"latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    return {"static_checks": _scored("static_checks", "(no model)", static_checks(inp["path"], inp["code"]),
                                     inp.get("gold", []), zero)}


def llm_reviewer_node(state: State) -> State:
    inp = state["input"]
    llm = chat_model(None, settings.AGENT_MAX_TOKENS).with_structured_output(
        {"title": "review", "type": "object",
         "properties": {"violations": {"type": "array", "items": {"type": "string", "enum": list(RULES)}}},
         "required": ["violations"], "additionalProperties": False},
        method="json_schema", strict=True, include_raw=True)
    out, call = metered_call("llm.review", llm, [SystemMessage(_SYSTEM),
                                                 HumanMessage(json.dumps({"path": inp["path"], "code": inp["code"]}))])
    got = out["parsed"].get("violations", []) if isinstance(out["parsed"], dict) else []
    flagged = [k for k in RULES if k in got]   # unknown ids dropped, order fixed
    return {"llm_reviewer": _scored("llm_reviewer", call["model"], flagged, inp.get("gold", []), call)}


NODES = {"jev": jev_node, "static_checks": static_checks_node, "llm_reviewer": llm_reviewer_node}


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
