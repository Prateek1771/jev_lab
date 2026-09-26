"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

const BEAT_MS = 15_000;   // api/presence.py BEAT_S; a visitor stops being live 40 s after their last beat
const fmt = new Intl.NumberFormat("en");

/** One random id per browser, so tabs and return visits count as one person. Storage can be blocked
    (private mode): then each page load counts as a new visitor, which is the honest best we can do. */
function visitorId(): string {
  try {
    const id = localStorage.getItem("jev-vid") ?? crypto.randomUUID();
    localStorage.setItem("jev-vid", id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

/** "● 3 live · 1,204 visitors" in the nav. Beats only while the tab is visible: a background tab isn't watching. */
export function LiveCounter() {
  const [c, setC] = useState<{ live: number; visitors: number } | null>(null);

  useEffect(() => {
    const id = visitorId();
    const beat = () => {
      if (document.visibilityState !== "visible") return;
      fetch(`${API_BASE}/api/presence`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ id }) })
        .then((r) => (r.ok ? r.json() : null))
        .then((b) => b && setC(b), () => {});   // API asleep or down: keep the last numbers, try again next beat
    };
    beat();
    const t = setInterval(beat, BEAT_MS);
    document.addEventListener("visibilitychange", beat);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", beat); };
  }, []);

  if (!c) return null;   // nothing until the first answer: a free API waking up shouldn't flash "0 live"
  return (
    <div className="fade-in flex items-center gap-1.5 whitespace-nowrap px-2 font-mono text-[12px] tracking-[0.04em] text-ink rule-l sm:gap-2 sm:px-3"
      title={`${c.live} watching now · ${c.visitors} people have visited`}>
      <span className="relative flex h-2 w-2" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-green" />
      </span>
      <span className="tabular-nums">{fmt.format(c.live)}<span className="hidden sm:inline"> live</span><span className="sr-only sm:hidden"> watching now</span></span>
      <span className="hidden text-gray lg:inline">·</span>
      <span className="hidden tabular-nums lg:inline">{fmt.format(c.visitors)} visitors</span>
    </div>
  );
}
