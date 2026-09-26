"""The refund policy as code. Pure: Jev's answers + facts computed in code in, exactly one decision out.
No I/O, no model calls: this is the part you can test exhaustively."""

# Starting values are the reference's defaults (jev_usecases/decisions.py, Thresholds).
# They are starting points, not truths: tune them on labeled rows like any other threshold.
HUMAN_CONFIDENCE = 0.45   # below this, nobody can act on the intent
AUTO_CONFIDENCE = 0.72    # an automatic refund needs a confident intent
POLICY_NO = 0.30          # P(policy supports the refund) below this: the policy says no
POLICY_AUTO = 0.85        # ... at or above this: supported enough to pay without a human
CHURN_HIGH = 1.5          # churn-risk score on 0..2; "leans high" keeps a human in the loop
MAX_PRIOR_REFUNDS = 2     # refunds in the last 30 days; counting is code's job, not Jev's

DECISIONS = ["refund_auto", "refund_confirm", "route_queue", "human", "block"]
BANDS = {"refund_auto": "auto", "route_queue": "auto", "refund_confirm": "confirm", "human": "human", "block": "block"}


def choose(intent: str, intent_conf: float, policy_ok: float, churn: float, facts: dict) -> tuple[str, str]:
    """Rules run most-cautious first, and the first match RETURNS. A later rule cannot overwrite an
    earlier escalation: the reference's customer_support.py sets a band, then reassigns it lines later."""
    if intent_conf < HUMAN_CONFIDENCE:
        return "human", f"intent unclear (confidence {intent_conf:.2f} < {HUMAN_CONFIDENCE})"
    if intent != "refund":
        return "route_queue", f"intent is {intent}, not a refund"
    if policy_ok < POLICY_NO:
        return "block", f"refund policy does not support it (P={policy_ok:.2f} < {POLICY_NO})"

    blockers = [reason for failed, reason in [
        (policy_ok < POLICY_AUTO, f"policy support {policy_ok:.2f} < {POLICY_AUTO}"),
        (intent_conf < AUTO_CONFIDENCE, f"intent confidence {intent_conf:.2f} < {AUTO_CONFIDENCE}"),
        (not facts["has_order"], "no order on file"),
        (facts["prior_refunds_30d"] >= MAX_PRIOR_REFUNDS, f"{facts['prior_refunds_30d']} refunds in 30 days"),
        (churn >= CHURN_HIGH, f"churn risk {churn:.2f} >= {CHURN_HIGH}"),
    ] if failed]
    if blockers:
        return "refund_confirm", "; ".join(blockers)
    return "refund_auto", "every automatic-refund condition holds"
