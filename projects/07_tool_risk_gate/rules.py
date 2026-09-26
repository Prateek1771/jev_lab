"""Deterministic denies. Pure. Run before Jev, because some calls should never depend on a judgment.
These are a floor, not a proof: they catch the obvious, Jev covers what no list anticipates."""

import re
import shlex

PROTECTED = {".env", ".git", ".ssh", "id_rsa", "id_ed25519"}   # whole path parts, never substrings
_UNBOUNDED = re.compile(r"^\s*(|1\s*=\s*1|true|1)\s*$", re.I)


def _path_parts(token: str) -> set[str]:
    return set(re.split(r"[/\\]", token))


def _shell_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:            # unbalanced quotes: treat as unparseable, and so as suspicious
        return ["<unparseable>"]


def hard_block(tool: str, args: dict) -> str | None:
    """A reason to block, or None. Checks the call's STRUCTURE (tokens, path parts, a WHERE clause),
    not a substring of the whole command: `.env` in `README.envision` is not a secrets file."""
    if tool == "delete_records" and _UNBOUNDED.match(str(args.get("where", ""))):
        return f"unbounded delete on {args.get('table')!r} (WHERE {args.get('where')!r})"

    if tool == "run_shell":
        tokens = _shell_tokens(str(args.get("command", "")))
        if tokens == ["<unparseable>"]:
            return "shell command could not be parsed"
        command = str(args.get("command", ""))
        if "$(" in command or "`" in command or "eval" in tokens or \
                ("base64" in tokens and any(t in ("-d", "--decode", "-D") for t in tokens)):
            # A path or command built at run time can't be checked here, so it doesn't run.
            # This closed the pinned gap `cat "$(echo LmVudg== | base64 -d)"` (= cat .env).
            return "command is built at run time (substitution, eval, or base64 decode)"
        for i, t in enumerate(tokens):
            flags = "".join(x.lstrip("-") for x in tokens[i + 1:] if x.startswith("-"))
            if t == "rm" and "r" in flags.lower() and "f" in flags and any(x in ("/", "~", "/*", "*") for x in tokens[i + 1:]):
                return "rm -rf on a root, home, or wildcard path"
        if "|" in tokens and any(t in ("curl", "wget") for t in tokens) and any(t in ("sh", "bash") for t in tokens):
            return "downloads code and pipes it into a shell"

    for value in args.values():
        for token in _shell_tokens(str(value)) if tool == "run_shell" else str(value).split():
            hit = _path_parts(token.strip("'\"`,;:()")) & PROTECTED
            if hit:
                return f"touches a protected path ({', '.join(sorted(hit))})"
    return None
