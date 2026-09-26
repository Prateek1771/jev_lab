"use client";

import { useEffect, useState } from "react";
import { CodeBlock, Label, Panel, Pill } from "@/components/ui";
import { client } from "@/lib/api";

type PromptRow = { n: number; kind: string; model: string | null; prompt: string; user: string; count: number };
type Prompts = { example: string | null; captured: string | null; missing: boolean; rows: PromptRow[] };

/** Every system prompt the experiment sends (recorded from a real run, so prompts built inside the code are here
    too), then one button for everything: the Excel workbook (dataset, examples, system prompts) plus the code. */
export function DownloadTab({ nn }: { nn: string }) {
  const [p, setP] = useState<Prompts | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  useEffect(() => { client<Prompts>(`/api/projects/${nn}/prompts`).then(setP); }, [nn]);
  if (!p) return <div className="h-24 animate-pulse bg-ink/10" />;

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h3 className="h3">What this experiment sends to each model</h3>
          {!p.missing && <Label className="text-gray">captured from a real run of “{p.example}” · {p.captured}</Label>}
        </div>
        {p.missing ? (
          <p className="font-mono text-[13px]">No prompts captured yet: run <code>uv run python scripts/capture_prompts.py {nn}</code></p>
        ) : p.rows.map((r) => (
          <Panel key={r.n}
            title={<span className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12px] text-viz-label">#{r.n}</span>
              <Pill t={r.kind === "Jev question" ? "magenta" : "blue"}>{r.kind}</Pill>
              {r.count > 1 && <span className="font-mono text-[11px] text-viz-label">×{r.count} per run</span>}
            </span>}
            right={<span className="flex items-center gap-3 font-mono text-[11px]">
              <span className="hidden sm:inline">{r.model}</span>
              <button type="button" className="text-viz-title hover:text-magenta"
                onClick={() => { navigator.clipboard?.writeText(r.prompt); setCopied(r.n); setTimeout(() => setCopied(null), 1500); }}>
                {copied === r.n ? "copied" : "copy"}
              </button>
            </span>}>
            <div className="space-y-2 px-4 pb-4">
              <CodeBlock>{r.prompt}</CodeBlock>
              {r.user && (
                <details className="font-mono text-[11px]">
                  <summary className="cursor-pointer text-viz-label hover:text-viz-title">input for this example</summary>
                  <div className="mt-2"><CodeBlock>{r.user}</CodeBlock></div>
                </details>
              )}
            </div>
          </Panel>
        ))}
      </div>

      {/* one button, at the bottom: the user asked for a single download */}
      <div className="flex flex-col items-start gap-2 border-t-[1.2px] border-ink pt-6">
        <a href={`/api/projects/${nn}/download/bundle.zip`} download
          className="border-[1.2px] border-ink bg-ink px-4 py-3 text-[16px] font-medium tracking-[0.03em] text-paper transition-colors duration-[400ms] ease-house hover:bg-magenta hover:text-ink">
          ↓ Download everything (.zip)
        </a>
        <p className="max-w-[70ch] font-mono text-[12px] leading-[1.5] text-gray">
          An Excel workbook with three sheets (Dataset, Examples, System prompts), plus the raw prompts.json,
          the dataset as CSV and JSON, and the experiment&apos;s code and about.md.{" "}
          <a href={`/api/projects/${nn}/download/workbook.xlsx`} download className="u text-ink">Or just the Excel workbook</a>.
        </p>
      </div>
    </div>
  );
}
