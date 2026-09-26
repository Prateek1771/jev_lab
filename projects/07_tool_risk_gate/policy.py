"""The gate's decision. Pure: the hard-rule result and Jev's four answers in, one decision out."""

# Starting values from the reference (decisions.py Thresholds; coding_agent_guardrails raises noul_yes to 0.75).
CLEAR_NO = 0.15       # P <= this: Jev is clearly saying "no"
CLEAR_YES = 0.85      # P >= this: clearly "yes"
SURE = 0.75           # P >= this: sure enough to go ahead without a person
UNSURE = 0.45         # the severity Score's own confidence below this: don't trust the severity
SEVERE = 1.0          # severity on 0..2 (low, medium, high): medium or worse

DECISIONS = ["allow", "confirm", "block"]
BANDS = {"allow": "auto", "confirm": "confirm", "block": "block"}


def decide(hard: str | None, a: dict | None) -> tuple[str, str]:
    """Most severe rule first, and the first match RETURNS. `a` is None when a hard rule already decided."""
    if hard:
        return "block", f"hard rule: {hard}"
    if a["in_scope"] <= CLEAR_NO:
        return "block", f"not what the user asked for (P in scope {a['in_scope']:.2f})"
    if a["leaks_sensitive"] >= CLEAR_YES:
        return "block", f"sends sensitive data out (P {a['leaks_sensitive']:.2f})"
    if a["severity_conf"] < UNSURE:
        return "confirm", f"unsure how bad a mistake would be (confidence {a['severity_conf']:.2f})"
    if a["in_scope"] < SURE:
        return "confirm", f"not clearly in scope (P {a['in_scope']:.2f} < {SURE})"
    if a["leaks_sensitive"] > CLEAR_NO:
        return "confirm", f"might expose sensitive data (P {a['leaks_sensitive']:.2f})"
    if a["reversible"] < SURE and a["severity"] >= SEVERE:
        return "confirm", f"hard to undo (P {a['reversible']:.2f}) and severity {a['severity']:.2f}"
    return "allow", "in scope, no sensitive data, and cheap to undo or low stakes"


def actions(decision: str, tool: str) -> list[str]:
    return {"allow": [f"execute:{tool}"], "confirm": [f"ask_user:{tool}"],
            "block": [f"deny:{tool}", "log:blocked"]}[decision]
