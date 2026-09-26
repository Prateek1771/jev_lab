"""The agent's tools. Offline, deterministic fakes: this project measures which tool gets picked,
so a tool's output only has to be believable and repeatable. Nothing here sends, buys, or deletes."""

import ast
import operator

WEATHER = {"paris": "14°C, light rain", "tokyo": "22°C, clear", "london": "11°C, overcast",
           "new york": "18°C, windy"}
ORDERS = {"A-104": {"status": "delivered", "items": 3, "subtotal": 120.00, "shipping": 7.50},
          "B-220": {"status": "in transit", "items": 1, "subtotal": 49.99, "shipping": 0.00},
          "C-9": {"status": "processing", "items": 2, "subtotal": 64.00, "shipping": 5.00}}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _arith(node):
    """Numbers and + - * / ** % only. Names, calls and attributes are rejected: never eval() model output."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_arith(node.right)) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](_arith(node.left), _arith(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_arith(node.operand))
    what = type(node.op).__name__ if isinstance(node, (ast.BinOp, ast.UnaryOp)) else type(node).__name__
    raise ValueError(f"not allowed: {what} (use numbers and + - * / ** % only)")


def calculator(expression: str) -> str:
    """`^` means power here, as models (and people) write it: the real test's `2^31 - 1` was rejected as XOR."""
    try:
        return f"{_arith(ast.parse(expression.replace('^', '**'), mode='eval').body):.10g}"
    except (SyntaxError, ValueError, ZeroDivisionError) as e:
        return f"error: {e}"


def get_weather(city: str) -> str:
    return WEATHER.get(city.strip().lower(), f"no weather data for {city}")


# Canned facts for the dataset's search rows. The first version returned "a short article summarizing the
# answer" with no answer in it, and the real test's native agent searched 4 times in a row looking for one.
SEARCH = {("nobel", "physics"): "The 2025 Nobel Prize in Physics went to John Clarke, Michel H. Devoret and John M. Martinis, for macroscopic quantum tunnelling in an electric circuit.",
          ("population", "tokyo"): "Tokyo's population is about 14 million (city) and about 37 million (greater Tokyo area)."}


def search_web(query: str) -> str:
    q = query.lower()   # ponytail: canned results; a real search API slots in here
    hit = next((text for words, text in SEARCH.items() if all(w in q for w in words)), None)
    return f"Top result for '{query}': {hit}" if hit else f"No results for '{query}'."


def database(order_id: str) -> str:
    order = ORDERS.get(order_id.strip().upper())
    return str(order) if order else f"no order {order_id}"


def send_email(to: str, subject: str, body: str) -> str:
    # Says SENT: the first version said "RECORDED, not sent", and in the real test Jev read that as "not done
    # yet" and sent the same email again, up to 4 times. Nothing is actually sent (project 07 gates that).
    return f"Sent (simulated): email to {to}, subject '{subject}'"


def create_ticket(title: str, priority: str) -> str:
    return f"Created (simulated): ticket T-1001 '{title}' ({priority})"


def _schema(**props: str) -> dict:
    return {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
            "required": list(props), "additionalProperties": False}


# name -> (description Jev and the LLMs see, argument JSON schema, function)
TOOLS = {
    "get_weather": ("Current weather for a city", _schema(city="City name"), get_weather),
    "search_web": ("Search the web for facts, news, or anything not in our own systems",
                   _schema(query="Search query"), search_web),
    "calculator": ("Evaluate an arithmetic expression", _schema(expression="e.g. (120 + 7.5) * 1.2"), calculator),
    "database": ("Look up one of OUR orders by order id: status, items, subtotal, shipping",
                 _schema(order_id="e.g. A-104"), database),
    "send_email": ("Send an email", _schema(to="Recipient address", subject="Subject", body="Body"), send_email),
    "create_ticket": ("Open a support ticket for our team",
                      _schema(title="Short title", priority="low, normal, or high"), create_ticket),
}


def run_tool(name: str, args: dict) -> str:
    """Bad arguments become an observation the agent can see, not an exception that kills the run."""
    try:
        return TOOLS[name][2](**args)
    except TypeError as e:
        return f"error: bad arguments for {name}: {e}"
