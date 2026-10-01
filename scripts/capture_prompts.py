"""Record exactly what each experiment sends to the models: Jev questions, LLM system prompts, tool schemas.
Many prompts are built at call time (f-strings, per-route agents, inlined Jev questions), so reading constants
from the code would miss them. Instead this runs each project's first example for real and records the JSON body
of every request to OpenRouter. Only the body: headers carry the API key and are never read.

Writes projects/NN_*/prompts.json; the web UI's Download tab and the Excel workbook read it.
Usage: uv run python scripts/capture_prompts.py [NN ...]      (default: all projects; ~$0.03 for all 25)"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
KEYLIKE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|Bearer\s+\S{16,}")


def record(request: httpx.Request) -> dict | None:
    """One request → one normalised call, or None if it isn't a model call. Reads request.content only."""
    if request.url.host not in ("openrouter.ai", "api.openai.com") or not request.content:
        return None
    body = json.loads(request.content)
    if "questions" in body:   # Jev: the Decisions API
        return {"kind": "jev", "model": body.get("model"), "questions": body["questions"], "state": body.get("state")}
    if "messages" not in body:
        return None

    def text(m):
        c = m.get("content")
        return c if isinstance(c, str) else "\n".join(p.get("text", "") for p in c or [] if isinstance(p, dict))
    msgs = body["messages"]
    return {"kind": "llm", "model": body.get("model"),
            "system": [text(m) for m in msgs if m.get("role") in ("system", "developer")],
            "user": [text(m) for m in msgs if m.get("role") not in ("system", "developer")],
            "tools": [{"name": t["function"]["name"], "description": t["function"].get("description", "")}
                      for t in body.get("tools") or [] if t.get("function")],
            "response_format": body.get("response_format")}


def capture(nn: str, module) -> dict:
    calls = []
    send = httpx.Client.send

    def spy(self, request, *a, **kw):
        call = record(request)
        if call:
            calls.append(call)
        return send(self, request, *a, **kw)
    httpx.Client.send = spy
    try:
        name, example = next(iter(module.EXAMPLES.items()))
        module.run_experiment(example)
    finally:
        httpx.Client.send = send
    out = {"example": name, "captured": date.today().isoformat(), "calls": calls}
    if KEYLIKE.search(json.dumps(out)):
        raise RuntimeError(f"{nn}: a key-like string in the capture; nothing written")
    return out


def main(ids: list[str]) -> None:
    sys.path.insert(0, str(ROOT))
    from core.projects import discover
    projects = discover()
    for nn in ids or list(projects):
        m = projects[nn]
        out = capture(nn, m)
        path = Path(m.__file__).parent / "prompts.json"
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        kinds = [c["kind"] for c in out["calls"]]
        print(f"{nn}: {len(kinds)} calls ({kinds.count('jev')} Jev, {kinds.count('llm')} LLM) -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
