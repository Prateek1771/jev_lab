"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const STREAMLIT_URL = (process.env.NEXT_PUBLIC_STREAMLIT_URL ?? "http://localhost:8501").trim();
const LOCAL = STREAMLIT_URL.includes("localhost");
const START = "uv run python scripts/dev.py --ui streamlit";

/** "New UI | Streamlit": the same experiment, in whichever UI you prefer. Streamlit's own health route
    tells us if it is running; when it isn't, the toggle says how to start it instead of opening a dead tab. */
export function UiToggle() {
  const nn = /^\/p\/(\d\d)/.exec(usePathname() ?? "")?.[1];
  const href = nn ? `${STREAMLIT_URL}/?p=${nn}` : STREAMLIT_URL;
  const [up, setUp] = useState<boolean | null>(null);
  const [hint, setHint] = useState(false);
  const [copied, setCopied] = useState(false);

  const check = useCallback(() => {
    // no-cors: the response is opaque, but it only resolves if something answered on that port
    fetch(`${STREAMLIT_URL}/_stcore/health`, { mode: "no-cors", cache: "no-store" }).then(() => setUp(true), () => setUp(false));
  }, []);

  useEffect(() => {
    check();
    window.addEventListener("focus", check);
    return () => window.removeEventListener("focus", check);
  }, [check]);

  const dot = up == null ? "bg-gray" : up ? "bg-green" : "bg-red";
  const cell = "flex items-center gap-1.5 whitespace-nowrap px-2.5 text-[13px] font-medium tracking-[0.03em] sm:px-3 sm:text-[14px]";

  return (
    <div className="relative flex shrink-0 rule-l" role="group" aria-label="Choose the UI">
      <span className={`${cell} bg-ink text-paper max-sm:hidden`} aria-current="true">New<span className="hidden sm:inline">&nbsp;UI</span></span>
      <a
        href={up ? href : undefined}
        onClick={(e) => {
          if (!up) { e.preventDefault(); check(); setHint((h) => !h); }
        }}
        title={up ? `Open ${nn ? `experiment ${nn}` : "Jev Lab"} in Streamlit` : "Streamlit isn't running"}
        className={`${cell} cursor-pointer rule-l text-ink transition-colors duration-500 ease-house hover:bg-ink hover:text-paper`}
      >
        <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} />
        Streamlit
      </a>
      {hint && !up && (
        <div className="fade-in absolute top-full right-0 z-50 mt-[1px] w-[400px] max-w-[92vw] border-[1.2px] border-ink bg-paper p-3 text-[14px] text-ink-86">
          {!LOCAL ? (
            <p className="mb-2"><b className="text-ink">Streamlit is waking up.</b> It runs on a free server that sleeps when idle; give it about a minute, then check again.</p>
          ) : (<>
          <p className="mb-2"><b className="text-ink">Streamlit isn&apos;t running.</b> Start it in another terminal, then click the toggle again:</p>
          <div className="flex items-stretch">
            <code className="flex-1 overflow-x-auto bg-ink px-2 py-1.5 font-mono text-[11.5px] whitespace-nowrap text-page">{START}</code>
            <button type="button" className="border-[1.2px] border-ink px-2 font-mono text-[11px] hover:bg-magenta"
              onClick={() => { navigator.clipboard?.writeText(START); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
              {copied ? "copied" : "copy"}
            </button>
          </div>
          </>)}
          <button type="button" onClick={check} className="mt-2 font-mono text-[11px] text-gray hover:text-magenta">check again ↻</button>
        </div>
      )}
    </div>
  );
}
