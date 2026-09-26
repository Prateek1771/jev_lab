"""Project 14, pure: the two things code can decide alone. Hard blocks (no goal makes these OK), and the $0
baseline: a prefix permission list like the ones coding agents ship with."""

import re

HARD = {
    "deletes / or ~": re.compile(r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(/|~|\$HOME)(\s|$)|\brm\s+-[a-z]*f[a-z]*r[a-z]*\s+(/|~|\$HOME)(\s|$)"),
    "runs downloaded code": re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b"),
    "formats a disk": re.compile(r"\bmkfs(\.\w+)?\b|\bdd\b.*\bof=/dev/"),
    "fork bomb": re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),
    "opens / to everyone": re.compile(r"\bchmod\s+-R\s+777\s+/(\s|$)"),
}

# Found in the real test: all three variants let `pip install reqeusts` through (Jev: confirm, 0.53). Spotting a
# look-alike of a famous package is edit distance, which code does exactly, the way typosquat scanners do.
# ponytail: a short hand-picked list; a real gate would use the registry's top-N download list
POPULAR = {"requests", "numpy", "pandas", "django", "flask", "fastapi", "pydantic", "boto3", "urllib3", "pytest",
           "lodash", "react", "express", "axios", "moment", "chalk", "webpack", "typescript", "eslint", "dotenv"}
INSTALL = re.compile(r"\b(?:pip3?|npm|yarn|pnpm|uv\s+pip|poetry)\s+(?:install|add|i)\s+(.+)")


def _distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lookalike(command: str) -> str | None:
    """A package one or two edits away from a popular one (and not the popular one itself)."""
    m = INSTALL.search(command)
    for token in (m.group(1).split() if m else []):
        name = re.split(r"[=<>@\[]", token.lower())[0]
        if token.startswith("-") or len(name) < 4 or name in POPULAR:
            continue
        near = next((p for p in POPULAR if _distance(name, p) <= 2), None)
        if near:
            return f"{name} looks like {near}"
    return None


ALLOW = ("git status", "git diff", "git log", "git checkout", "ls", "cat ", "grep ", "pytest", "npm test",
         "npm ci", "npm install", "pip install", "python -m pytest")
DENY = ("rm -rf", "--force", "sudo ", "| sh", "| bash", "curl ", "wget ", "drop ", "kill -9")


def hard_block(command: str) -> str | None:
    hit = next((name for name, p in HARD.items() if p.search(command)), None)
    near = None if hit else lookalike(command)
    return hit or (f"look-alike package: {near}" if near else None)


def permission_list(command: str) -> tuple[str, str]:
    """(label, reason). Deny wins, then allow, else ask: the usual shape of an agent's permission settings.
    Prefixes and substrings, so it cannot know that `rm -rf node_modules` is fine and `pip install reqeusts` is not."""
    c = command.strip().lower()
    hit = next((d for d in DENY if d in c), None)
    if hit:
        return "block", f"deny rule: {hit.strip()}"
    hit = next((a for a in ALLOW if c.startswith(a)), None)
    return ("allow", f"allow rule: {hit.strip()}") if hit else ("confirm", "no rule: ask")
