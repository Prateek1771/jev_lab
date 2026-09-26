"""Project 19, pure: the ideal customer profile, what code checks (company size), how two Scores become a CRM route,
and the $0 baseline: points-based lead scoring, the way marketing tools do it."""

import re

ICP = {
    "industries": "fintech, banking, payments, or e-commerce with a payment-fraud problem",
    "company_size": "50 to 2,000 employees",
    "buyers": "engineering, fraud, risk or security leaders, or someone buying on their behalf",
    "pains": "false positives, alert fatigue, the cost of manual fraud review",
    "disqualifiers": "fewer than 10 employees, students or researchers, competitors, no budget",
}
SIZE = (50, 2000)
JEV_ICP = {k: v for k, v in ICP.items() if k != "company_size"}   # what code checks, the model is not asked
# Real test, first run: "strong" demanded evidence of pain, which an inbound message rarely states (a CISO asking
# for pricing scored 1.23), and the profile's size range made Jev fold size into fit. Pain is now a plus, and
# the size range is not in Jev's profile at all: code checks it (JEV_ICP above).
FIT_LEVELS = ["Not a fit: wrong industry or buyer, or a disqualifier applies (competitor, student, tiny, no budget)",
              "Partial fit: industry or buyer is only adjacent to the profile",
              "Strong fit: industry and buyer match the profile, no disqualifier applies (a stated pain is a plus)"]
INTENT_LEVELS = ["No buying intent: browsing, learning, or unrelated", "Exploring: interested, no timeline",
                 "Active: evaluating now, asking for a demo, trial, quote or pricing with a timeline"]


def route(fit: float, intent: float, employees: int) -> str:
    """Code, not a third question: disqualify, sales now, or nurture."""
    if employees < 10 or fit < 0.5:
        return "disqualify"
    if fit >= 1.5 and intent >= 1.5 and SIZE[0] <= employees <= SIZE[1]:
        return "sales_now"
    return "nurture"


def points(lead: dict) -> tuple[str, int]:
    """Classic MQL scoring: +points for title, industry words, size, 'demo/pricing' words. Words, not meaning."""
    p = 0
    p += 25 * bool(re.search(r"\b(vp|head|director|chief|cto|ciso)\b", lead["title"], re.I))
    p += 20 * bool(re.search(r"fintech|bank|payment|fraud|e-?commerce", lead["company"], re.I))
    p += 15 * (SIZE[0] <= lead["employees"] <= SIZE[1])
    p += 30 * bool(re.search(r"\b(demo|pricing|price|quote|trial|evaluat\w*)\b", lead["message"], re.I))
    p -= 40 * bool(re.search(r"@(gmail|yahoo|hotmail|outlook)\.", lead.get("email", ""), re.I))
    return ("sales_now" if p >= 70 else "nurture" if p >= 35 else "disqualify"), p
