"""The nav's live counter: who is on the site now, and how many different people have ever visited.

Each open tab sends a heartbeat with its browser's random visitor id (web/components/LiveCounter.tsx) every
BEAT_S seconds while visible; a visitor is "live" until LIVE_S passes without one. Deployed, the counts live in
Render Key Value (REDIS_URL) so a sleeping or redeployed API keeps them; locally they live in this process.
ponytail: ids come from the browser, so a script can inflate the counts. It's a vanity number; per-IP caps if that matters."""

import re
import time

from config import settings

BEAT_S, LIVE_S = 15, 40
ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

_redis = None
if settings.REDIS_URL:
    import redis
    _redis = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=3)
_live: dict[str, float] = {}   # local fallback: id -> last beat
_seen: set[str] = set()


def beat(vid: str) -> dict[str, int]:
    now = time.time()
    if _redis:
        p = _redis.pipeline()
        p.zadd("live", {vid: now})
        p.zremrangebyscore("live", "-inf", now - LIVE_S)
        p.zcard("live")
        p.pfadd("visitors", vid)   # HyperLogLog: a fixed 12 KB however many visit, ~1% off at scale
        p.pfcount("visitors")
        res = p.execute()
        return {"live": res[2], "visitors": res[4]}
    _live[vid] = now
    for k in [k for k, t in _live.items() if t < now - LIVE_S]:
        del _live[k]
    _seen.add(vid)
    return {"live": len(_live), "visitors": len(_seen)}
