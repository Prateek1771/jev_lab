"""Project 20, pure: the facts code computes from a (synthetic) transaction, and the $0 baseline, a rules engine."""


def features(tx: dict) -> dict:
    """Arithmetic and lookups, never asked of a model."""
    return {
        "amount_vs_usual": round(tx["amount"] / max(tx["usual_amount"], 1), 1),
        "new_device": tx["device"] == "new",
        "foreign": tx["country"] != tx["home_country"],
        "travel_notice": tx.get("travel_notice", False),
        "tx_last_hour": tx.get("tx_last_hour", 0),
        "shipping_changed_today": tx.get("shipping_changed_today", False),
    }


def rules(tx: dict) -> tuple[str, str]:
    """A classic rules engine: thresholds on the same facts, first match wins."""
    f = features(tx)
    if f["tx_last_hour"] >= 5:
        return "investigate", "velocity: 5+ transactions in an hour"
    if f["new_device"] and f["foreign"] and tx["amount"] >= 500:
        return "investigate", "new device + foreign + $500 or more"
    if f["amount_vs_usual"] >= 5 or (f["foreign"] and not f["travel_notice"]) or f["new_device"]:
        return "review", "amount 5x usual, foreign without notice, or new device"
    return "allow", "no rule matched"
