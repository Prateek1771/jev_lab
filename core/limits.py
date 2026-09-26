"""Spam caps on the paid calls, shared by the API and the Streamlit app: per visitor per hour, and for everyone
per day (settings, 0 = off).
ponytail: in memory, per process, reset on restart: fine for one Render instance each, Redis if it ever scales out.
The API and Streamlit are separate processes, so each gets its own caps. The IP can be faked, so the per-day cap
is the real spend guard."""

import time
from collections import defaultdict, deque

from config import settings

_hits: dict[str, deque[float]] = defaultdict(deque)   # "run:1.2.3.4" / "run:all" -> call times


def over_limit(kind: str, ip: str) -> str | None:
    """Count one `kind` ("run" or "dataset") call from `ip`; the refusal message if a cap is hit, else None."""
    now, counted = time.time(), []
    for key, cap, window, per in ((f"{kind}:{ip}", getattr(settings, f"{kind.upper()}_LIMIT_PER_IP_HOUR"), 3600, "per hour"),
                                  (f"{kind}:all", getattr(settings, f"{kind.upper()}_LIMIT_PER_DAY"), 86400, "per day, for everyone")):
        if not cap:
            continue
        hits = _hits[key]
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= cap:
            wait = max(1, round((hits[0] + window - now) / 60))
            return f"Limit reached: {cap} {'runs' if kind == 'run' else 'dataset runs'} {per}. Try again in {wait} min."
        counted.append(hits)
    for hits in counted:
        hits.append(now)
    return None
