"use client";

import { useState } from "react";
import { ValueBars } from "@/components/charts";
import { Button, Chip, Label, Panel } from "@/components/ui";
import { client } from "@/lib/api";
import { ms, seriesColor, usd } from "@/lib/format";
import type { ProjectDetail, ResultJson } from "@/lib/types";
import { VariantCard } from "./VariantCard";

export function RunTab({ project }: { project: ProjectDetail }) {
  const names = Object.keys(project.examples);
  const [example, setExample] = useState(names[0]);
  const toText = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v, null, 2));
  const [text, setText] = useState(toText(project.examples[names[0]]));
  const structured = typeof project.examples[example] !== "string";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ResultJson | null>(null);

  function pick(name: string) {
    setExample(name);
    setText(toText(project.examples[name]));
  }

  async function run() {
    setError("");
    let input: unknown = text;
    if (structured) {
      try {
        input = JSON.parse(text);
      } catch (e) {
        setError(`Input is not valid JSON: ${(e as Error).message}`); // never send a half-edited input
        return;
      }
    }
    setBusy(true);
    try {
      setResult(await client<ResultJson>(`/api/projects/${project.id}/run`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ input }),
      }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const bars = (key: "latency_ms" | "cost_usd") =>
    (result?.runs ?? []).filter((r) => r[key] != null).map((r) => ({ name: r.title.replace(/ \(.+\)$/, ""), value: r[key] as number, color: seriesColor(r.variant, String(r.model).startsWith("(") ? "free" : "llm") }));

  return (
    <div className="space-y-6">
      <div className="grid gap-5 lg:grid-cols-[1fr_auto]">
        <div className="space-y-3">
          <Label>Examples</Label>
          <div className="flex flex-wrap gap-2">
            {names.map((n) => <Chip key={n} active={n === example} onClick={() => pick(n)}>{n}</Chip>)}
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            rows={structured ? 9 : 4}
            className="w-full resize-y border-[1.2px] border-ink bg-paper/60 p-3 font-mono text-[13px] leading-[1.5] text-ink outline-none focus:bg-paper"
          />
        </div>
        <div className="flex flex-col justify-end gap-2 lg:w-[220px]">
          <p className="font-mono text-[11px] leading-[1.4] text-gray">
            Calls Jev and every baseline for real{project.traced ? ", traced in Langfuse" : ""}. Nothing is saved.
          </p>
          <Button solid onClick={run} disabled={busy}>{busy ? <span className="blink">Running…</span> : "Run experiment →"}</Button>
        </div>
      </div>

      {error && <p className="border-[1.2px] border-red bg-paper/50 px-3 py-2 font-mono text-[13px] text-red">{error}</p>}

      {result && (
        <div className="fade-in space-y-5">
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${result.runs.length > 3 ? 240 : 300}px, 1fr))` }}>
            {result.runs.map((r) => <VariantCard key={r.variant} run={r} />)}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="Latency">
              <ValueBars data={bars("latency_ms")} format={ms} />
            </Panel>
            <Panel title="Cost" hint="lower is better">
              <ValueBars data={bars("cost_usd")} format={usd} />
            </Panel>
          </div>
          {result.trace_url && (
            <a href={result.trace_url} target="_blank" rel="noreferrer" className="u inline-block font-mono text-[13px] text-ink">
              Open this run&apos;s trace in Langfuse ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}
