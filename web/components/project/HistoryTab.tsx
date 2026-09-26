"use client";

import { useEffect, useState } from "react";
import { Label } from "@/components/ui";
import { client } from "@/lib/api";
import { pct, usd } from "@/lib/format";
import type { RunMeta } from "@/lib/types";
import { DiffView, ReportView } from "./ReportView";

export function HistoryTab({ nn, refresh }: { nn: string; refresh: number }) {
  const [runs, setRuns] = useState<RunMeta[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);

  useEffect(() => {
    client<RunMeta[]>(`/api/projects/${nn}/runs`).then((r) => {
      setRuns(r);
      setOpen((o) => o ?? r[0]?.file ?? null);
    });
  }, [nn, refresh]);

  if (!runs) return <div className="h-24 animate-pulse bg-ink/10" />;
  if (!runs.length) return <p className="text-[15px]">No saved runs yet. Run the dataset and it lands here.</p>;

  const toggle = (f: string) => setPicked((p) => (p.includes(f) ? p.filter((x) => x !== f) : [...p.slice(-1), f]));
  const [a, b] = [...picked].sort();

  return (
    <div className="space-y-8">
      <div className="border-t-[1.2px] border-ink">
        <div className="hidden grid-cols-[28px_120px_1fr_90px_90px_1.4fr] gap-3 rule-b py-2 md:grid">
          {["", "date", "run", "rows", "spend", "jev · best other"].map((h) => <Label key={h} className="text-gray">{h}</Label>)}
        </div>
        {runs.map((r) => {
          const hs = Object.entries(r.headline);
          const score = (h: (typeof hs)[number][1]) => (h.graded ? h.pass_rate : h.accuracy);
          const jev = r.headline.jev;
          const other = hs.filter(([k]) => k !== "jev").sort(([, x], [, y]) => (score(y) ?? 0) - (score(x) ?? 0))[0];
          return (
            <div key={r.file} className={`grid grid-cols-[28px_1fr] items-center gap-3 rule-b py-2.5 md:grid-cols-[28px_120px_1fr_90px_90px_1.4fr] ${open === r.file ? "bg-paper/40" : ""}`}>
              <input type="checkbox" aria-label={`compare ${r.file}`} checked={picked.includes(r.file)} onChange={() => toggle(r.file)} className="h-4 w-4 accent-[#d45bb6]" />
              <button type="button" onClick={() => setOpen(r.file)} className="text-left font-mono text-[13px] text-ink hover:text-magenta md:col-auto">{r.date}</button>
              <button type="button" onClick={() => setOpen(r.file)} className="col-start-2 text-left text-[15px] text-ink hover:underline md:col-start-auto">{r.label}</button>
              <span className="col-start-2 font-mono text-[12px] md:col-start-auto">{r.rows}{r.errors ? ` (${r.errors} failed)` : ""}</span>
              <span className="col-start-2 font-mono text-[12px] md:col-start-auto">{usd(r.spend)}</span>
              <span className="col-start-2 font-mono text-[12px] md:col-start-auto">
                <b className="text-ink">{pct(jev ? score(jev) : null)}</b>
                {other && <span className="text-gray"> · {other[1].title}: {pct(score(other[1]))}</span>}
              </span>
            </div>
          );
        })}
      </div>

      {picked.length === 2 ? (
        <section className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h3 className="h3">Then → now, row by row</h3>
            <button type="button" onClick={() => setPicked([])} className="font-mono text-[12px] text-gray hover:text-magenta">clear comparison ×</button>
          </div>
          <DiffView nn={nn} a={a} b={b} />
        </section>
      ) : (
        <p className="font-mono text-[12px] text-gray">Tick two runs to diff them row by row.</p>
      )}

      {open && (
        <section className="space-y-3">
          <h3 className="h3">Report</h3>
          <ReportView key={open} nn={nn} file={open} />
        </section>
      )}
    </div>
  );
}
