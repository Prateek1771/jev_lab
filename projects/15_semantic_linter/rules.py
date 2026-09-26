"""Project 15: the team's four rules (one definition, used by Jev and the LLM reviewer alike), the $0 static
checks a semgrep/bandit config would run, and per-rule precision/recall against the gold violations."""

import re

from shared.metrics import precision_recall  # noqa: F401  (moved to shared/ in Phase 21: third copy)

RULES = {
    "auth_bypass": {
        "instructions": "code lets a request reach protected data or actions without the team's auth check",
        "criteria": {"true": "A route that returns or changes user data with no @require_auth, or a debug flag, "
                             "header or parameter that skips the check",
                     "false": "Public endpoints (health, login, static pages), routes that keep the auth check, "
                              "or code that is not a request handler"}},
    # Real test, first run: "logs, returns or STORES" overlapped hardcoded_secret (a key in source scored 0.66 on
    # both). One judgment per rule: this one is about data leaving at run time; secrets in source are the next rule.
    "sensitive_exposure": {
        "instructions": "code sends secrets or personal data to logs, error messages or API responses",
        "criteria": {"true": "Passwords, tokens, hashes, emails or card data in logs, error messages or API "
                             "responses",
                     "false": "Masked or truncated values, booleans or counts about them, sending data to the "
                              "place it belongs, or a credential written in source (that is hardcoded_secret)"}},
    "layering": {
        "instructions": "route or controller code talks to the database directly instead of through the "
                        "repository layer",
        "criteria": {"true": "A file under routes/ or api/ that runs queries, sessions, cursors or ORM managers",
                     "false": "Routes that call a repository or service, or database code inside repositories/"}},
    "hardcoded_secret": {
        "instructions": "code contains a real credential as a literal",
        "criteria": {"true": "A working-looking key, token, password or connection string with a password, "
                             "in source",
                     "false": "Values read from the environment or a secret manager, obvious test placeholders "
                              "in tests/, or example values in docs"}},
}

STATIC = {   # what a pattern-based linter can express
    "auth_bypass": lambda path, code: bool(re.search(r"@app\.(get|post|put|delete)\(", code))
                                      and "@require_auth" not in code,
    "sensitive_exposure": lambda path, code: bool(re.search(r"\b(log\w*(\.\w+)?|print)\(.*(password|token|secret)", code, re.I)),
    "layering": lambda path, code: path.startswith(("routes/", "api/"))
                                   and bool(re.search(r"\b(db\.session|session\.query|cursor\.|\.execute\()", code)),
    "hardcoded_secret": lambda path, code: bool(re.search(
        r"(sk-(live|test)-\w{8,}|AKIA[A-Z0-9]{16}|(password|secret|api_key)\s*=\s*[\"'][^\"']+[\"'])", code, re.I)),
}


def static_checks(path: str, code: str) -> list[str]:
    return [rule for rule, check in STATIC.items() if check(path, code)]
