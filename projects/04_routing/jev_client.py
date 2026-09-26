"""Jev side of project 04: three questions about one ticket, answered in ONE Decisions call."""

from config import settings
from shared.openrouter import decide


def ask_ticket(state: dict, intents: dict[str, str]) -> dict:
    """Returns the three answers plus the call's metadata. The decision is made elsewhere (policy.py)."""
    body, latency = decide(state, {
        "intent": {"type": "choice", "instructions": "What is the customer's primary intent?", "criteria": intents},
        "policy_supports_refund": {
            "type": "noul",
            "instructions": ("Given refund_policy, order and within_return_window, the stated refund policy "
                             "supports the refund the customer asks for in message"),
            "criteria": {"true": "The request matches a case the policy says is eligible",
                         "false": "The policy excludes it, or no refund is being asked for"},
        },
        "churn_risk": {"type": "score", "instructions": "How likely is this customer to leave, from their message?",
                       "criteria": ["Low", "Moderate", "High"]},
    })
    a, usage = body["answers"], body.get("usage") or {}
    return {
        "intent": a["intent"]["choice"],
        "intent_conf": float(a["intent"]["confidence"]),
        "policy_ok": float(a["policy_supports_refund"]["noul"]),
        "churn": float(a["churn_risk"]["score"]),
        "model": body.get("model", settings.JEV_MODEL),
        "latency_ms": latency,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": usage.get("cost"),
        "id": body.get("id"),
    }
