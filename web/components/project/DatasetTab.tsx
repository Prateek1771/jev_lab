"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Label, Pill } from "@/components/ui";
import { API_BASE } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";
import { ReportView } from "./ReportView";

type Row = { idx: number; text: string; expected: string; error: string | null; got: Record<string, string> | null };

/** POST + a streamed body, parsed as server-sent events (EventSource can only GET). */
async function* events(res: Response) {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      const event = /^event: (.+)$/m.exec(block)?.[1];
      const data = /^data: (.+)$/m.exec(block)?.[1];
      if (event && data) yield { event, data: JSON.parse(data) };
    }
  }
}

const clock = (ms: number) => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

export function DatasetTab({ project, onSaved }: { project: ProjectDetail; onSaved: () => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(project.rows);
  const [running, setRunning] = useState(false);
  const [file, setFile] = useState<string | null>(null);
  const [error, setError] = useState("");
  const tail = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState<{ idx: number; text: string } | null>(null);
  const [started, setStarted] = useState(0);
  const [now, setNow] = useState(0);
  const [took, setTook] = useState(0);

  useEffect(() => {   // a 1s tick while running, for the elapsed time and the ETA
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);

  async function run() {
    setRows([]); setFile(null); setError(""); setRunning(true); setCurrent(null);
    const t0 = Date.now();
    setStarted(t0); setNow(t0);
    try {
      const res = await fetch(`${API_BASE}/api/projects/${project.id}/dataset`, { method: "POST" });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `${res.status} ${res.statusText}`);
      for await (const { event, data } of events(res)) {
        if (event === "start") setTotal(data.rows);
        if (event === "working") setCurrent(data);
        if (event === "row") {
          setRows((r) => [...r, data]);
          requestAnimationFrame(() => tail.current?.scrollIntoView({ block: "nearest" }));
        }
        if (event === "done") { setFile(data.file); setTook(Date.now() - t0); onSaved(); }
      }
    } catch (e) {
      setError(`${(e as Error).message}. Rows finished so far are saved in History.`);
    } finally {
      setRunning(false);
      setCurrent(null);
    }
  }

  const variants = rows.find((r) => r.got)?.got ? Object.keys(rows.find((r) => r.got)!.got!) : [];
  const correct = (v: string) => rows.filter((r) => r.got?.[v] === r.expected).length;
  const elapsed = Math.max(0, now - started);
  const eta = rows.length >= 2 ? (elapsed / rows.length) * (total - rows.length) : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <p className="max-w-[62ch] text-[15px] leading-[1.4]">
          Runs every labeled row, one at a time: <b className="text-ink">{project.rows} rows × every variant</b>, all real, paid calls.
          Rows run sequentially so latency measures the model, not a traffic jam. The run is saved as it goes and lands in History.
        </p>
        <Button solid onClick={run} disabled={running}>{running ? <span className="blink">Running… {rows.length}/{total}</span> : "Run dataset →"}</Button>
      </div>

      {error && <p className="border-[1.2px] border-red px-3 py-2 font-mono text-[13px] text-red">{error}</p>}

      {running && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-[1.2px] border-ink bg-paper/50 px-3 py-2 font-mono text-[12px] text-ink" role="status" aria-live="polite">
          <span className="relative flex h-2 w-2 shrink-0"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-magenta opacity-75" /><span className="relative inline-flex h-2 w-2 rounded-full bg-magenta" /></span>
          {current ? (
            <span className="min-w-0 flex-1 truncate">
              Row {String(current.idx + 1).padStart(2, "0")} of {total} <span className="text-gray">·</span> &ldquo;{current.text}&rdquo;
            </span>
          ) : <span className="flex-1">Starting…</span>}
          <span className="text-gray">{rows.length} done · {clock(elapsed)}{eta != null ? ` · ~${clock(eta)} left` : ""}</span>
        </div>
      )}

      {(running || (rows.length > 0 && !file)) && (
        <div className="space-y-3">
          <div className="h-[3px] w-full bg-ink/15"><div className="h-full bg-magenta transition-[width] duration-300" style={{ width: `${(rows.length / total) * 100}%` }} /></div>
          {variants.length > 0 && (
            <div className="flex flex-wrap gap-4 font-mono text-[12px]">
              {variants.map((v) => <span key={v}><span className="text-gray">{v}</span> <b className="text-ink">{correct(v)}/{rows.length}</b></span>)}
            </div>
          )}
          <div className="max-h-[360px] overflow-auto border-t-[1.2px] border-ink">
            {rows.map((r) => (
              <div key={r.idx} className="fade-in grid grid-cols-[36px_1fr] gap-3 rule-b py-2 md:grid-cols-[36px_1fr_auto]">
                <span className="font-mono text-[12px] text-gray">{String(r.idx).padStart(2, "0")}</span>
                <span className="truncate text-[14px] text-ink">{r.text}</span>
                <span className="col-start-2 flex flex-wrap gap-1 md:col-start-auto">
                  {r.error ? <Pill t="red">error</Pill> : Object.entries(r.got ?? {}).map(([v, g]) => (
                    <span key={v} title={`${v}: ${g} (expected ${r.expected})`}><Pill t={g === r.expected ? "green" : "red"}>{g}</Pill></span>
                  ))}
                </span>
              </div>
            ))}
            <div ref={tail} />
          </div>
        </div>
      )}

      {file && (
        <div className="space-y-3">
          <Label>Done: {rows.length} rows in {clock(took)} · saved as {file}</Label>
          <ReportView nn={project.id} file={file} />
        </div>
      )}
    </div>
  );
}
