"use client";

import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { HEX } from "@/lib/format";

const axis = { stroke: HEX.border, tick: { fill: HEX.label, fontSize: 11, fontFamily: "var(--font-mono)" }, tickLine: false };
const tipStyle = {
  contentStyle: { background: "#1e1e1e", border: `1px solid ${HEX.border}`, borderRadius: 0, fontFamily: "var(--font-mono)", fontSize: 12 },
  labelStyle: { color: HEX.title },
  itemStyle: { color: HEX.label },
  cursor: { stroke: HEX.border },
};

export function Legend({ items }: { items: { color: string; label: string; shape?: "square" | "diamond" | "circle" | "line" }[] }) {
  return (
    <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px] text-viz-title">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-2">
          {it.shape === "line" ? (
            <span className="inline-block h-px w-5" style={{ background: it.color }} />
          ) : (
            <span
              className="inline-block h-2.5 w-2.5"
              style={{ background: it.color, transform: it.shape === "diamond" ? "rotate(45deg) scale(.85)" : undefined, borderRadius: it.shape === "circle" ? 999 : 0 }}
            />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}

// ---------- Accuracy vs cost (the reference's "accuracy vs cost" log scatter) ----------

export type ScatterPoint = { project: string; name: string; variant: string; title: string; kind: string; cost: number; acc: number; graded: boolean };
const FREE_X = 3e-7; // $0 can't sit on a log axis: free baselines get their own column at the far left

function Mark(props: { cx?: number; cy?: number; payload?: ScatterPoint }) {
  const { cx = 0, cy = 0, payload } = props;
  if (!payload) return null;
  const color = payload.kind === "jev" ? HEX.magenta : payload.kind === "free" ? HEX.sage : /frontier|always_review|ladder/.test(payload.variant) ? HEX.orange : HEX.teal;
  if (payload.kind === "jev") return <rect x={cx - 5} y={cy - 5} width={10} height={10} fill={color} transform={`rotate(45 ${cx} ${cy})`} stroke="#1e1e1e" strokeWidth={1} />;
  return <circle cx={cx} cy={cy} r={4.5} fill={color} stroke="#1e1e1e" strokeWidth={1} opacity={0.9} />;
}

export function CostAccuracyScatter({ points, height = 440, onPick }: { points: ScatterPoint[]; height?: number; onPick?: (p: ScatterPoint) => void }) {
  const data = points.map((p) => ({ ...p, x: p.cost > 0 ? p.cost : FREE_X, y: p.acc * 100 }));
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const check = () => setNarrow(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  const ticks = narrow ? [FREE_X, 1e-5, 1e-3, 1e-1] : [FREE_X, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1];
  const lo = Math.max(0, Math.floor((Math.min(...data.map((d) => d.y), 100) - 3) / 10) * 10);
  const yTicks = Array.from({ length: (100 - lo) / 10 + 1 }, (_, i) => lo + i * 10);
  const fmt = (v: number) => (v === FREE_X ? "free" : `$${v.toFixed(Math.max(0, -Math.floor(Math.log10(v))))}`);
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 26, left: 0 }}>
          <CartesianGrid stroke={HEX.grid} />
          <XAxis
            type="number" dataKey="x" scale="log" domain={[FREE_X / 1.5, 0.2]} ticks={ticks} tickFormatter={fmt} {...axis}
            label={{ value: "cost per decision, USD (log)", position: "insideBottom", offset: -16, fill: HEX.label, fontSize: 12 }}
          />
          <YAxis type="number" dataKey="y" domain={[lo, 100]} ticks={yTicks} tickFormatter={(v) => `${v}%`} {...axis} width={48} />
          <ZAxis range={[60, 60]} />
          <Tooltip
            {...tipStyle}
            content={({ payload }) => {
              const p = payload?.[0]?.payload as (ScatterPoint & { x: number; y: number }) | undefined;
              if (!p) return null;
              return (
                <div className="border border-viz-border bg-ink px-3 py-2 font-mono text-[12px] text-viz-label">
                  <div className="text-viz-title">{p.project} · {p.name}</div>
                  <div>{p.title}</div>
                  <div>{p.graded ? "pass rate" : "accuracy"} {p.y.toFixed(0)}% · {p.cost > 0 ? `$${p.cost.toPrecision(2)}` : "free"} / decision</div>
                </div>
              );
            }}
          />
          <Scatter data={data} shape={<Mark />} onClick={(d) => onPick?.(d as unknown as ScatterPoint)} className="cursor-pointer" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------- Bars with the value printed on top (the reference's error-rate bars) ----------

export function ValueBars({ data, format, height = 190 }: { data: { name: string; value: number; color: string }[]; format: (v: number) => string; height?: number }) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 22, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid stroke={HEX.grid} vertical={false} />
          <XAxis dataKey="name" {...axis} interval={0} tick={{ ...axis.tick, fontSize: 10 }} />
          <YAxis hide />
          <Tooltip {...tipStyle} formatter={(v) => format(Number(v))} />
          <Bar dataKey="value" radius={[2, 2, 0, 0]} maxBarSize={46} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.name} fill={d.color} />)}
            <LabelList dataKey="value" position="top" formatter={(v) => format(Number(v))} fill={HEX.title} fontSize={11} fontFamily="var(--font-mono)" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------- Threshold sweep ----------

export function SweepChart({ points, best, value }: { points: { threshold: number; fn: number; fp: number; cost?: number; accuracy: number | null }[]; best: number; value: string }) {
  return (
    <div style={{ height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 10, right: 16, bottom: 22, left: 0 }}>
          <CartesianGrid stroke={HEX.grid} />
          <XAxis dataKey="threshold" type="number" domain={["dataMin", "dataMax"]} {...axis}
            label={{ value: `threshold on ${value}`, position: "insideBottom", offset: -12, fill: HEX.label, fontSize: 12 }} />
          <YAxis {...axis} width={36} allowDecimals={false} />
          <Tooltip {...tipStyle} />
          <ReferenceLine x={best} stroke={HEX.magenta} strokeDasharray="3 3" />
          <Line type="stepAfter" dataKey="fn" name="missed" stroke={HEX.red} dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="fp" name="false alarms" stroke={HEX.blue} dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="cost" name="mistake cost" stroke={HEX.sage} dot={false} strokeWidth={1} strokeDasharray="4 3" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
