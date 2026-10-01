"use client";

import { useEffect, useRef, useState } from "react";
import { Chessboard } from "react-chessboard";
import { Button, CodeBlock, Panel, ProbBar } from "@/components/ui";
import { API_BASE } from "@/lib/api";
import { HEX, ms, usd } from "@/lib/format";
import type { ProjectDetail } from "@/lib/types";
import { events } from "./DatasetTab";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const EVAL = ["Black is winning", "Black is better", "Equal", "White is better", "White is winning"];

type JevResponse = { answers?: {
  move?: { choice: string; confidence: number; probabilities: Record<string, number> };
  eval?: { score: number }; threat?: { noul: number };
} };
type Side = "white" | "black";
type Ply = {
  ply: number; side: Side; player: string; model: string; uci: string; san: string; piece: string;
  from: string; to: string; captured: string | null; fen: string; result: string | null;
  latency_ms: number; cost_usd: number | null; input_tokens: number; output_tokens: number;
  reason: string | null; request: unknown; response: JevResponse | null; fallback: boolean;
};

const name = (p: string) => (p === "jev" ? "Jev 1.13" : p === "heuristic" ? "Heuristic (no model)" : p);
const color = (p: string) => (p === "jev" ? HEX.magenta : p === "heuristic" ? HEX.sage : HEX.teal);

function PlayerSelect({ side, value, onChange, players, disabled }: {
  side: Side; value: string; onChange: (v: string) => void; players: string[]; disabled: boolean;
}) {
  return (
    <label className="flex items-stretch border-[1.2px] border-ink">
      <span className="flex w-[84px] shrink-0 items-center gap-2 px-3 cap text-ink">
        <span className={`inline-block size-2.5 border border-ink ${side === "white" ? "bg-paper" : "bg-ink"}`} />{side}
      </span>
      <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}
        className="min-w-0 flex-1 rule-l bg-paper/60 px-3 py-2.5 font-mono text-[13px] text-ink outline-none focus:bg-paper disabled:opacity-60">
        {players.map((p) => <option key={p} value={p}>{name(p)}</option>)}
      </select>
    </label>
  );
}

export function PlayTab({ project }: { project: ProjectDetail }) {
  const players = project.players ?? [];
  const [white, setWhite] = useState("jev");
  const [black, setBlack] = useState(players.find((p) => p !== "jev" && p !== "heuristic") ?? players[0]);
  const [plies, setPlies] = useState<Ply[]>([]);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [sel, setSel] = useState<number | null>(null);   // null = follow live
  const [tab, setTab] = useState<"request" | "response">("request");
  const abort = useRef<AbortController | null>(null);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {   // follow live: keep the newest move in view, inside the list only (never scroll the page)
    if (sel === null && list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [plies, sel]);

  async function play() {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setPlies([]); setSel(null); setError(""); setPlaying(true);
    try {
      const res = await fetch(`${API_BASE}/api/projects/${project.id}/play`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ white, black }), signal: ctl.signal,
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `${res.status} ${res.statusText}`);
      for await (const { event, data } of events(res)) {
        if (event === "move") setPlies((p) => [...p, data]);
        if (event === "error") setError(data.message);
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setPlaying(false);
    }
  }

  const stop = () => abort.current?.abort();
  const shown = sel !== null ? plies[sel] : plies[plies.length - 1];
  const result = plies[plies.length - 1]?.result;
  const status = result ?? (playing ? `${name(plies.length % 2 ? black : white)} to move` : plies.length ? "Stopped" : "Pick two players and press Play");

  const totals = (side: Side) => {
    const ps = plies.filter((p) => p.side === side);
    const sum = (f: (p: Ply) => number) => ps.reduce((a, p) => a + f(p), 0);
    return { n: ps.length, cost: sum((p) => p.cost_usd ?? 0), tin: sum((p) => p.input_tokens), tout: sum((p) => p.output_tokens),
      lat: ps.length ? sum((p) => p.latency_ms) / ps.length : null, fb: ps.filter((p) => p.fallback).length };
  };
  const t = { white: totals("white"), black: totals("black") };
  const jev = shown?.player === "jev" ? shown.response?.answers : null;
  const top3 = jev ? Object.entries(jev.move?.probabilities ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 3) : [];

  const strip = (side: Side) => {
    const p = side === "white" ? white : black;
    return (
      <div className="flex items-baseline justify-between gap-3 px-1 py-2 font-mono text-[12px] text-viz-label">
        <span className="flex items-center gap-2 text-viz-title">
          <span className="inline-block size-2.5" style={{ background: color(p) }} />{name(p)}
        </span>
        <span>{t[side].n} moves · {usd(t[side].cost)}</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)]">
        <Panel className="pt-2">
          {strip("black")}
          <div className="mx-auto w-full max-w-[560px]">
            <Chessboard options={{
              position: shown?.fen ?? START, allowDragging: false, animationDurationInMs: 250,
              lightSquareStyle: { backgroundColor: "#dfe5e4" }, darkSquareStyle: { backgroundColor: "#7f9695" },
              squareStyles: shown ? { [shown.from]: { background: "rgba(212,91,182,.35)" }, [shown.to]: { background: "rgba(212,91,182,.55)" } } : {},
              arrows: shown ? [{ startSquare: shown.from, endSquare: shown.to, color: color(shown.player) }] : [],
            }} />
          </div>
          {strip("white")}
        </Panel>

        <div className="flex min-w-0 flex-col gap-4">
          <PlayerSelect side="white" value={white} onChange={setWhite} players={players} disabled={playing} />
          <PlayerSelect side="black" value={black} onChange={setBlack} players={players} disabled={playing} />
          <div className="flex flex-wrap items-center gap-3">
            {playing ? <Button onClick={stop}>Stop</Button> : <Button solid onClick={play}>Play a game →</Button>}
            {sel !== null && <Button onClick={() => setSel(null)}>Follow live</Button>}
            <span className={`font-mono text-[13px] text-ink ${playing && !result ? "blink" : ""}`}>{status}</span>
          </div>
          <p className="font-mono text-[11px] leading-[1.4] text-gray">
            Every move is a real paid call (up to 300 plies). Jev runs on OpenRouter, the LLM on OpenAI with your
            OPENAI_API_KEY. Nothing is saved.
          </p>
          {error && <p className="border-[1.2px] border-red bg-paper/50 px-3 py-2 font-mono text-[13px] text-red">{error}</p>}

          <Panel title="Moves" right={<span className="font-mono text-[11px]">{plies.length} plies</span>} className="min-w-0">
            <div ref={list} className="max-h-[300px] overflow-y-auto font-mono text-[12px]">
              {!plies.length && <p className="py-6 text-center">Moves stream here.</p>}
              {plies.map((p, i) => (
                <button key={i} type="button" onClick={() => setSel(i)}
                  className={`grid w-full grid-cols-[42px_minmax(0,1fr)_auto] items-baseline gap-2 border-b border-viz-grid px-1 py-1.5 text-left transition-colors duration-200 hover:bg-viz-grid ${(sel ?? plies.length - 1) === i ? "bg-viz-grid text-viz-title" : ""}`}>
                  <span>{Math.ceil(p.ply / 2)}{p.side === "white" ? "." : "…"}</span>
                  <span className="truncate">
                    <b className="text-viz-title" style={{ color: color(p.player) }}>{p.san}</b>{" "}
                    {p.piece} {p.from}→{p.to}{p.captured ? ` ×${p.captured}` : ""}
                    {p.fallback && <span className="ml-1.5 text-orange" title="No legal move from the model: a random one was played">fallback</span>}
                  </span>
                  <span className="text-right">{usd(p.cost_usd)} · {ms(p.latency_ms)}</span>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="Totals" className="min-w-0">
            <div className="overflow-x-auto">
              <table className="w-full font-mono text-[12px]">
                <thead><tr className="text-left text-viz-label"><th className="py-1 font-normal">Player</th><th className="font-normal">Moves</th><th className="font-normal">Cost</th><th className="font-normal">Tokens in/out</th><th className="font-normal">Avg</th></tr></thead>
                <tbody className="text-viz-title">
                  {(["white", "black"] as const).map((s) => (
                    <tr key={s} className="border-t border-viz-grid">
                      <td className="py-1.5 pr-2">{name(s === "white" ? white : black)}{t[s].fb ? <span className="ml-1 text-orange">{t[s].fb} fb</span> : null}</td>
                      <td>{t[s].n}</td><td>{usd(t[s].cost)}</td>
                      <td>{t[s].tin.toLocaleString()}/{t[s].tout.toLocaleString()}</td><td>{ms(t[s].lat)}</td>
                    </tr>
                  ))}
                  <tr className="border-t border-viz-border"><td className="py-1.5">Game</td><td>{plies.length}</td><td>{usd(t.white.cost + t.black.cost)}</td>
                    <td>{(t.white.tin + t.black.tin).toLocaleString()}/{(t.white.tout + t.black.tout).toLocaleString()}</td><td /></tr>
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>

      {shown && (
        <Panel className="fade-in min-w-0" title={`Move ${shown.ply}: ${shown.san}`}
          right={<span className="font-mono text-[11px]">{shown.model} · {shown.input_tokens} in / {shown.output_tokens} out · {usd(shown.cost_usd)}</span>}>
          {shown.reason && <p className="mb-3 text-[14px] text-viz-title">“{shown.reason}”</p>}
          {jev && (
            <div className="mb-4 grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <p className="font-mono text-[11px] uppercase tracking-[0.07em] text-viz-label">Choice · top 3</p>
                {top3.map(([k, v]) => <ProbBar key={k} label={k} value={v} />)}
              </div>
              <div className="space-y-2">
                <p className="font-mono text-[11px] uppercase tracking-[0.07em] text-viz-label">Score · eval</p>
                <ProbBar label={EVAL[Math.round(jev.eval?.score ?? 2)] ?? "?"} value={jev.eval?.score ?? 0} max={4} color={HEX.violet} />
              </div>
              <div className="space-y-2">
                <p className="font-mono text-[11px] uppercase tracking-[0.07em] text-viz-label">Noul · a piece is hanging</p>
                <ProbBar label="P(true)" value={jev.threat?.noul ?? 0} color={HEX.orange} />
              </div>
            </div>
          )}
          {shown.request != null && (
            <>
              <div className="mb-2 flex">
                {(["request", "response"] as const).map((k, i) => (
                  <button key={k} type="button" onClick={() => setTab(k)}
                    className={`border border-viz-border px-3 py-1 font-mono text-[11px] uppercase tracking-[0.07em] ${i ? "border-l-0" : ""} ${tab === k ? "bg-viz-title text-ink" : "text-viz-label hover:text-viz-title"}`}>{k}</button>
                ))}
              </div>
              <div className="max-h-[420px] overflow-y-auto">
                <CodeBlock>{JSON.stringify(tab === "request" ? shown.request : shown.response, null, 2)}</CodeBlock>
              </div>
            </>
          )}
        </Panel>
      )}
    </div>
  );
}
