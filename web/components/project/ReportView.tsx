"use client";

import { useEffect, useState } from "react";
import { Legend, SweepChart, ValueBars } from "@/components/charts";
import { Label, Panel, Pill } from "@/components/ui";
import { client } from "@/lib/api";
import { HEX, ms, num, pct, seriesColor, usd } from "@/lib/format";
import type { Diff, Report, RunMeta, SavedRow, VariantSummary } from "@/lib/types";
import { VariantCard } from "./VariantCard";

type Line = { label: string; cells: (string | number)[]; strong?: boolean };

/** Editorial comparison table: mono uppercase row labels, one column per variant, dashed rules, no zebra. */
export function CompareTable({ heads, lines }: { heads: { key: string; title: string }[]; lines: Line[] }) {
  return (
    <div className="overflow-x-auto border-t-[1.2px] border-ink">
      <table className="w-full min-w-[560px] border-collapse text-left">
        <thead>
          <tr className="rule-b">
            <th className="w-[220px] py-2 pr-3" />
            {heads.map((h) => (
              <th key={h.key} className="px-3 py-2 align-bottom text-[14px] font-medium text-ink">
                {h.key === "jev" && <span className="mr-1.5 inline-block h-2 w-2 rotate-45 bg-magenta" />}
                {h.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => (
            <tr key={l.label} className="rule-b">
              <td className="py-2 pr-3"><Label>{l.label}</Label></td>
              {l.cells.map((c, i) => (
                <td key={i} className={`px-3 py-2 font-mono text-[13px] ${l.strong ? "text-[15px] font-medium text-ink" : "text-ink-86"}`}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function summaryLines(r: Report): Line[] {
  const vs = r.variants.map((v) => r.summary[v.key]);
  const lines: Line[] = [
    { label: "Accuracy", cells: vs.map((s) => pct(s.accuracy)), strong: true },
    { label: "Correct", cells: vs.map((s) => `${s.correct}/${s.rows - s.errors}`) },
    { label: "Invalid answers", cells: vs.map((s) => s.invalid) },
    { label: "p50 latency", cells: vs.map((s) => ms(s.p50_ms)) },
    { label: "p95 latency", cells: vs.map((s) => ms(s.p95_ms)) },
    { label: "Total cost", cells: vs.map((s) => usd(s.total_cost)) },
  ];
  if (vs.some((s) => s.cost_missing)) lines.push({ label: "Rows missing cost", cells: vs.map((s) => s.cost_missing) });
  if (vs.some((s) => s.graded)) {
    lines.push({ label: "Passing grader", cells: vs.map((s) => `${s.passed}/${s.graded}`), strong: true });
    lines.push({ label: "Pass rate", cells: vs.map((s) => pct(s.pass_rate)) });
    lines.push({ label: "Cost per pass", cells: vs.map((s) => usd(s.cost_per_pass)) });
  }
  for (const m of r.raw_metrics) {
    lines.push({ label: m.label, cells: vs.map((s) => (s[m.key] == null ? "n/a" : m.pct ? pct(s[m.key] as number) : num(s[m.key] as number))) });
  }
  if (r.safety_names) {
    const [caught, allowed, stopped] = r.safety_names;
    const g = (s: VariantSummary) => s.safety!;
    lines.push({ label: caught, cells: vs.map((s) => `${g(s).unsafe_blocked}/${g(s).unsafe} (${pct(g(s).block_rate)})`) });
    lines.push({ label: allowed, cells: vs.map((s) => g(s).unsafe_allowed), strong: true });
    lines.push({ label: stopped, cells: vs.map((s) => `${g(s).safe_stopped}/${g(s).safe} (${pct(g(s).false_positive_rate)})`) });
  }
  return lines;
}

/** Every variant's full saved answer for one row: the Run tab's cards, replayed from disk for free. */
function SavedRowCards({ nn, file, idx }: { nn: string; file: string; idx: number }) {
  const [row, setRow] = useState<SavedRow | null>(null);
  useEffect(() => {
    client<SavedRow>(`/api/projects/${nn}/runs/${encodeURIComponent(file)}/rows/${idx}`).then(setRow);
  }, [nn, file, idx]);
  if (!row) return <div className="h-24 animate-pulse bg-ink/10" />;
  return (
    <div className="fade-in mt-3 grid gap-3" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${row.runs.length > 3 ? 240 : 280}px, 1fr))` }}>
      {row.runs.map((r) => <VariantCard key={r.variant} run={r} />)}
      {row.trace_url && <a href={row.trace_url} target="_blank" rel="noreferrer" className="u font-mono text-[12px] text-ink">trace ↗</a>}
    </div>
  );
}

export function ReportView({ nn, file, initial }: { nn: string; file: string; initial?: { meta: RunMeta; report: Report } }) {
  const [data, setData] = useState(initial ?? null);
  const [costs, setCosts] = useState({ fn: 5, fp: 1 });
  const [error, setError] = useState("");
  const [inspect, setInspect] = useState<number | null>(null);

  useEffect(() => {
    client<{ meta: RunMeta; report: Report }>(`/api/projects/${nn}/runs/${encodeURIComponent(file)}?cost_fn=${costs.fn}&cost_fp=${costs.fp}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [nn, file, costs]);

  if (error) return <p className="font-mono text-[13px] text-red">{error}</p>;
  if (!data) return <div className="h-40 animate-pulse bg-ink/10" />;
  const { report: r, meta } = data;
  const graded = r.variants.some((v) => r.summary[v.key].graded);
  const headline = (v: string) => (graded ? r.summary[v].pass_rate : r.summary[v].accuracy) ?? 0;
  const kindOf = (v: string) => meta.headline[v]?.kind;
  const done = r.variants.length ? r.summary[r.variants[0].key].rows - r.summary[r.variants[0].key].errors : 0;

  return (
    <div className="fade-in space-y-8">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 font-mono text-[12px] text-gray">
        <span className="text-ink">{meta.label}</span>
        <span>{meta.date}</span>
        <span>{meta.rows} rows</span>
        {meta.errors > 0 && <span className="text-red">{meta.errors} failed (excluded)</span>}
        <span>spend {usd(meta.spend)}</span>
        {done > 0 && <span>one row = {pct(1 / done)} · differences of a row or two are noise</span>}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title={graded ? "Pass rate" : "Accuracy"} hint="higher is better">
          <ValueBars data={r.variants.map((v) => ({ name: v.title.replace(/ \(.+\)$/, ""), value: headline(v.key), color: seriesColor(v.key, kindOf(v.key)) }))} format={(x) => pct(x)} />
        </Panel>
        <Panel title="Total cost" hint="lower is better">
          <ValueBars data={r.variants.map((v) => ({ name: v.title.replace(/ \(.+\)$/, ""), value: r.summary[v.key].total_cost, color: seriesColor(v.key, kindOf(v.key)) }))} format={usd} />
        </Panel>
      </div>

      <CompareTable heads={r.variants} lines={summaryLines(r)} />

      <div className="grid gap-10">
        <div>
          <Label className="mb-2">Label counts</Label>
          <CompareTable heads={r.variants}
            lines={r.label_keys.map((k) => ({ label: k, cells: r.variants.map((v) => r.summary[v.key].labels[k] ?? 0) }))} />
          <p className="mt-2 font-mono text-[11px] text-gray">A label that never appears: the model never picked it, or the code can&apos;t produce it.</p>
        </div>
        <div>
          <Label className="mb-2">{r.wrong.length} row(s) where a variant was wrong · click one to see every answer</Label>
          <div className="border-t-[1.2px] border-ink">
            {r.wrong.map((w) => (
              <div key={w.idx} className="rule-b py-2.5">
                <button type="button" onClick={() => setInspect(inspect === w.idx ? null : w.idx)} className="mb-1.5 block w-full text-left text-[14px] text-ink hover:text-magenta">
                  <span className="mr-2 font-mono text-[11px] text-gray">#{w.idx} {inspect === w.idx ? "▾" : "▸"}</span>{w.text}
                </button>
                <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                  <span className="text-gray">expected</span> <Pill t="gray">{w.expected}</Pill>
                  {r.variants.map((v) => (
                    <span key={v.key} className="inline-flex items-center gap-1">
                      <span className="text-gray">{v.key}</span>
                      <Pill t={w.got[v.key] === w.expected ? "green" : "red"}>{w.got[v.key]}</Pill>
                    </span>
                  ))}
                  {w.jev_value != null && <span className="text-gray">jev value {w.jev_value.toFixed(2)}</span>}
                  {w.error && <span className="text-red">{w.error}</span>}
                </div>
                {inspect === w.idx && <SavedRowCards nn={nn} file={file} idx={w.idx} />}
              </div>
            ))}
          </div>
        </div>
      </div>

      {r.sweep && (
        <Panel title="Threshold sweep" hint="re-decided from this run's stored values, no API calls"
          right={
            <div className="flex items-center gap-3 font-mono text-[11px]">
              {(["fn", "fp"] as const).map((k) => (
                <label key={k} className="flex items-center gap-1.5">
                  {k === "fn" ? `missed ${r.sweep!.positive}` : "false alarm"} costs
                  <input type="number" min={0} step={1} value={costs[k]} onChange={(e) => setCosts({ ...costs, [k]: Number(e.target.value) })}
                    className="w-12 border border-viz-border bg-ink px-1.5 py-0.5 text-viz-title outline-none focus:border-magenta" />
                </label>
              ))}
            </div>
          }>
          <Legend items={[{ color: HEX.red, label: "missed", shape: "line" }, { color: HEX.blue, label: "false alarms", shape: "line" }, { color: HEX.sage, label: "mistake cost", shape: "line" }, { color: HEX.magenta, label: "cheapest threshold", shape: "line" }]} />
          <SweepChart points={r.sweep.points} best={r.sweep.best.threshold} value={r.sweep.value} />
          <p className="mt-2 text-[14px] text-viz-title">
            Cheapest on these rows: <b className="text-magenta">{r.sweep.value} ≥ {r.sweep.best.threshold}</b> · missed {r.sweep.best.fn}, false alarms {r.sweep.best.fp}, accuracy {pct(r.sweep.best.accuracy)}.
          </p>
          <p className="mt-1 font-mono text-[11px]">Picked on the same rows it is scored on, so it is optimistic. Confirm on rows it never saw.</p>
        </Panel>
      )}
    </div>
  );
}

export function DiffView({ nn, a, b }: { nn: string; a: string; b: string }) {
  const [d, setD] = useState<Diff | null>(null);
  useEffect(() => {
    client<Diff>(`/api/projects/${nn}/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`).then(setD);
  }, [nn, a, b]);
  if (!d) return <div className="h-24 animate-pulse bg-ink/10" />;
  const graded = d.variants.some((v) => v.after.graded);
  return (
    <div className="fade-in space-y-5">
      <CompareTable
        heads={[{ key: "then", title: a.slice(0, 10) + " · " + a.split("_").slice(2).join(" ").replace(".json", "") }, { key: "now", title: b.slice(0, 10) + " · " + b.split("_").slice(2).join(" ").replace(".json", "") }, { key: "cost", title: "cost then → now" }]}
        lines={d.variants.map((v) => ({
          label: v.title,
          cells: graded
            ? [`${v.before.passed}/${v.before.graded} pass`, `${v.after.passed}/${v.after.graded} pass`, `${usd(v.before.cost)} → ${usd(v.after.cost)}`]
            : [`${v.before.correct}/${v.before.rows}`, `${v.after.correct}/${v.after.rows}`, `${usd(v.before.cost)} → ${usd(v.after.cost)}`],
        }))}
      />
      <div>
        <Label className="mb-2">{d.changed.length ? `${d.changed.length} changed row(s)` : "No row changed: fully reproduced"}</Label>
        {d.changed.map((c, i) => (
          <div key={i} className="grid gap-1 rule-b py-2.5 md:grid-cols-[1fr_auto] md:items-center">
            <div className="text-[14px] text-ink"><span className="mr-2 font-mono text-[11px] text-gray">#{c.idx} {c.variant}</span>{c.text}</div>
            <div className="flex items-center gap-1.5 font-mono text-[11px]">
              <Pill t={c.before === c.expected ? "green" : "red"}>{c.before ?? "none"}</Pill>→<Pill t={c.after === c.expected ? "green" : "red"}>{c.after ?? "none"}</Pill>
              {c.q_before != null && <span className="text-gray">q {c.q_before.toFixed(2)} → {c.q_after?.toFixed(2)}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
