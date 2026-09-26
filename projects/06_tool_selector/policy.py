"""What the agent does after a selector's pick. Pure: pick in, one step out. No I/O, no model calls."""

UNSURE = 0.45    # the reference's human_confidence: below this, ask the user instead of guessing a tool
MAX_STEPS = 4    # tool calls per request; the graph's loop edge stops there, and the run counts as unfinished

STOPS = {"finish": "The observations so far already answer the request, or no tool is needed",
         "ask_user": "The request is unclear, or is missing something a tool would need"}


def next_step(choice: str, conf: float | None) -> tuple[str, str]:
    """Returns (step, reason): a tool name, "finish", or "ask_user". First match returns.
    conf is None for selectors that report no confidence (the LLM ones), so only Jev can be gated."""
    if conf is not None and conf < UNSURE:
        return "ask_user", f"unsure which tool (confidence {conf:.2f} < {UNSURE})"
    if choice in STOPS:
        return choice, f"selector chose {choice}"
    return choice, "tool chosen" if conf is None else f"tool chosen (confidence {conf:.2f})"


def trajectory(tools_called: list[str], stop: str | None) -> str | None:
    """The run's label: "database > calculator", "none" (answered without tools), "... > ask_user".
    None when the loop hit MAX_STEPS without stopping: an agent that never finishes has no answer."""
    if stop is None:
        return None
    return " > ".join(tools_called + (["ask_user"] if stop == "ask_user" else [])) or "none"
