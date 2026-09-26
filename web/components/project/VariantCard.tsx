"use client";

import { useState } from "react";
import { Markdown } from "@/components/Markdown";
import { CodeBlock, Pill, ProbBar } from "@/components/ui";
import { HEX, ms, usd } from "@/lib/format";
import type { RunJson } from "@/lib/types";

type Step = { tool: string; args: unknown; result: unknown; gate?: string; filtered?: string };
type Claim = { verdict: string; text: string; code?: string | null; checks: { source: string; choice: string; confidence: number }[] };

const short = (v: unknown, n = 260) => {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > n ? `${s.slice(0, n)}…` : s;
};

/** One variant's answer, as the Streamlit page showed it, on an instrument panel. */
export function VariantCard({ run }: { run: RunJson }) {
  const raw = run.raw as Record<string, unknown>;
  const [open, setOpen] = useState(false);
  const human = run.outcome === "(human)";
  const steps = raw.steps as Step[] | undefined;
  const claims = raw.claims as Claim[] | undefined;
  const levels = (raw.levels as number | undefined) ?? 3;
  const isJev = run.variant === "jev";

  return (
    <article className={`flex flex-col gap-3 rounded-[8px] border bg-viz p-4 text-viz-label ${isJev ? "border-magenta/70" : "border-viz-border"}`}>
      <header>
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-[15px] font-medium text-viz-title">{run.title}</h3>
          {isJev && <span className="font-mono text-[10px] tracking-[0.1em] text-magenta">JEV</span>}
        </div>
        <div className="mt-0.5 truncate font-mono text-[11px]">{run.model}</div>
      </header>

      <div className="flex min-h-[34px] items-center">
        {human ? <Pill t="blue" big>sent to a human</Pill> : run.label ? <Pill big>{run.label}</Pill> : <Pill t="red" big>outside the schema</Pill>}
      </div>

      <div className="space-y-2.5">
        {run.confidence != null && <ProbBar label="confidence" value={run.confidence} color={HEX.sage} />}
        {run.probability != null && <ProbBar label={`P(${(raw.p_of as string) ?? "yes"})`} value={run.probability} color={HEX.magenta} />}
        {run.score != null && <ProbBar label="score" value={run.score} max={levels - 1} color={HEX.violet} />}
        {run.quality != null && (
          <ProbBar label="grader: P(correct)" value={run.quality} color={run.quality >= 0.5 ? HEX.green : HEX.red} note={run.quality >= 0.5 ? "pass" : "fail"} />
        )}
      </div>

      {raw.finish_reason === "length" && (
        <p className="border border-orange/60 px-2 py-1 font-mono text-[11px] text-orange">Answer cut off at the token cap: its grade is unreliable.</p>
      )}

      {typeof raw.reason === "string" && raw.reason && (
        <p className="font-mono text-[12px] leading-[1.45] text-viz-title">
          {typeof raw.band === "string" && <span className="mr-1.5 text-magenta">band {raw.band} ·</span>}
          {raw.reason}
        </p>
      )}

      {Array.isArray(raw.actions) && <CodeBlock>{(raw.actions as string[]).join("\n")}</CodeBlock>}

      {steps && (
        <div>
          <div className="mb-1 font-mono text-[10px] tracking-[0.1em] text-viz-label">STEPS</div>
          <ol className="space-y-1.5 border border-viz-border bg-ink p-2.5 font-mono text-[11.5px] leading-[1.45]">
            {steps.map((s, i) => (
              <li key={i} className="break-words text-page [overflow-wrap:anywhere]">
                <span className="text-viz-label">{i + 1}.</span> <span className="text-viz-title">{s.tool}</span>
                <span className="text-viz-label">({short(s.args, 80)})</span>
                {s.gate && <span className="ml-1.5"><Pill>{s.gate}</Pill></span>}
                {s.filtered && <span className="ml-1.5 text-teal">{s.filtered}</span>}
                <div className="pl-4 text-viz-label">→ {short(s.result)}</div>
              </li>
            ))}
            <li className="text-viz-label">stop: <span className="text-viz-title">{String(raw.stop ?? "")}</span></li>
          </ol>
        </div>
      )}

      {typeof raw.redacted === "string" && (
        <div>
          <div className="mb-1 font-mono text-[10px] tracking-[0.1em]">WHAT THE LLM RECEIVES</div>
          <CodeBlock>{raw.redacted}</CodeBlock>
        </div>
      )}

      {claims && (
        <ol className="space-y-2 border border-viz-border bg-ink p-2.5 text-[12.5px]">
          {claims.map((c, i) => (
            <li key={i}>
              <div className="flex items-start gap-2"><Pill>{c.verdict}</Pill><span className="text-viz-title">{c.text}</span></div>
              <div className="mt-1 pl-1 font-mono text-[11px] text-viz-label">
                {c.code ?? c.checks.map((x) => `[${x.source}] ${x.choice} ${x.confidence.toFixed(2)}`).join(" · ")}
              </div>
            </li>
          ))}
        </ol>
      )}

      {typeof raw.answer === "string" && raw.answer && (
        <details className="group border-t border-viz-border pt-2" open>
          <summary className="cursor-pointer list-none font-mono text-[10px] tracking-[0.1em] text-viz-label hover:text-viz-title">
            <span className="group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span> ANSWER
          </summary>
          <div className="mt-2 max-h-[340px] overflow-y-auto pr-1"><Markdown dark>{raw.answer}</Markdown></div>
        </details>
      )}

      <footer className="mt-auto grid grid-cols-3 gap-2 border-t border-viz-border pt-2.5 font-mono text-[11px]">
        <div><div className="text-[9.5px] tracking-[0.1em]">LATENCY</div><div className="text-viz-title">{ms(run.latency_ms)}</div></div>
        <div><div className="text-[9.5px] tracking-[0.1em]">TOKENS</div><div className="text-viz-title">{run.input_tokens}+{run.output_tokens}</div></div>
        <div><div className="text-[9.5px] tracking-[0.1em]">COST</div><div className="text-viz-title">{usd(run.cost_usd)}</div></div>
      </footer>
      <button type="button" onClick={() => setOpen(!open)} className="self-start font-mono text-[10px] tracking-[0.1em] text-viz-label hover:text-magenta">
        {open ? "▾ RAW" : "▸ RAW"}
      </button>
      {open && <CodeBlock>{JSON.stringify(raw, null, 2)}</CodeBlock>}
    </article>
  );
}
