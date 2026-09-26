"""Jev side of project 06: which tool next, or stop. One Choice per step, traced as one generation."""

from shared.openrouter import decide_traced

from .policy import STOPS
from .tools import TOOLS


def pick_tool(request: str, observations: list[dict], tools: dict = TOOLS) -> dict:
    """ONE question for ONE judgment. The reference also asks a `should_call` Noul, a second copy of
    the choice's own "none" option; here stopping is simply an option of the same Choice.
    `tools` defaults to this project's; project 24 passes its own."""
    state = {"request": request, "observations": observations}
    question = {"type": "choice", "instructions": "What should the assistant do next to handle request?",
                "criteria": {name: desc for name, (desc, _, _) in tools.items()} | STOPS}
    a, meta = decide_traced("jev.pick_tool", state, {"next": question})
    return {"choice": a["next"]["choice"], "confidence": float(a["next"]["confidence"])} | meta
