import type { ReactNode } from "react";
import { HEX, TONE_COLOR, tone, type Tone } from "@/lib/format";

/** Outlined uppercase mono pill (the flow diagram's action pills): border and text in one accent colour. */
export function Pill({ children, t, big }: { children: ReactNode; t?: Tone; big?: boolean }) {
  const color = TONE_COLOR[t ?? tone(String(children))];
  return (
    <span
      className={`pill inline-flex items-center whitespace-nowrap rounded-full border font-mono uppercase ${big ? "px-3 py-1 text-[13px] tracking-[0.08em]" : "px-2 py-[1px] text-[10.5px] tracking-[0.07em]"}`}
      style={{ color, borderColor: color }}
    >
      {children}
    </span>
  );
}

/** The dark instrument panel every chart, diagram and result sits on. */
export function Panel({ title, hint, children, className = "", right }: { title?: ReactNode; hint?: string; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <section className={`rounded-[8px] border border-viz-border bg-viz text-viz-label ${className}`}>
      {(title || right) && (
        <header className="flex items-baseline justify-between gap-4 px-4 pt-3.5 pb-2">
          <h3 className="text-[15px] font-medium tracking-[0.01em] text-viz-title">
            {title}
            {hint && <span className="ml-1 font-normal text-viz-label">({hint})</span>}
          </h3>
          {right}
        </header>
      )}
      <div className="px-4 pb-4">{children}</div>
    </section>
  );
}

export function Label({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`cap ${className}`}>{children}</div>;
}

type BtnProps = { children: ReactNode; onClick?: () => void; disabled?: boolean; solid?: boolean; type?: "button" | "submit"; className?: string };
/** Outlined 1.2px ink, 0 radius; solid = ink with paper text. */
export function Button({ children, onClick, disabled, solid, type = "button", className = "" }: BtnProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`border-[1.2px] border-ink px-3.5 py-2.5 text-[15px] font-medium tracking-[0.03em] transition-colors duration-[400ms] ease-house disabled:cursor-not-allowed disabled:opacity-40 ${
        solid ? "bg-ink text-paper hover:bg-magenta hover:text-ink" : "bg-transparent text-ink hover:bg-ink hover:text-paper"
      } ${className}`}
    >
      {children}
    </button>
  );
}

/** Highlight chip: paper background, magenta on hover. */
export function Chip({ children, active, onClick }: { children: ReactNode; active?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-1.5 text-[14px] tracking-[0.02em] transition-colors duration-200 ease-house ${
        active ? "bg-ink text-paper" : "bg-paper text-ink-86 hover:bg-magenta"
      }`}
    >
      {children}
    </button>
  );
}

/** A row of outlined cells separated by dashed rules (the blog's meta row). */
export function MetaRow({ items }: { items: { k: string; v: ReactNode }[] }) {
  return (
    <div className="flex flex-wrap border-[1.2px] border-ink">
      {items.map((it, i) => (
        <div key={it.k} className={`flex flex-col gap-1 px-3 py-2 ${i ? "rule-l" : ""}`}>
          <span className="cap text-gray">{it.k}</span>
          <span className="text-[15px] text-ink">{it.v}</span>
        </div>
      ))}
    </div>
  );
}

/** A probability / confidence / grade bar on the dark panel. */
export function ProbBar({ label, value, max = 1, color = HEX.magenta, note }: { label: string; value: number; max?: number; color?: string; note?: string }) {
  const w = Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <div className="space-y-1">
      <div className="flex justify-between font-mono text-[11px] tracking-[0.05em] text-viz-label">
        <span>{label}</span>
        <span className="text-viz-title">
          {value.toFixed(2)}
          {max !== 1 && <span className="text-viz-label"> / {max}</span>}
          {note && <span className="ml-1.5 text-viz-label">{note}</span>}
        </span>
      </div>
      <div className="h-[5px] w-full bg-viz-grid">
        <div className="h-full" style={{ width: `${w}%`, background: color }} />
      </div>
    </div>
  );
}

export function CodeBlock({ children, dark = true }: { children: string; dark?: boolean }) {
  return (
    <pre
      className={`overflow-x-auto whitespace-pre-wrap break-words p-3 font-mono text-[12px] leading-[1.5] ${
        dark ? "border border-viz-border bg-ink text-page" : "border border-[rgba(153,153,153,.25)] bg-[rgba(153,153,153,.1)] text-[#333]"
      }`}
    >
      {children}
    </pre>
  );
}

/** The pixel brand glyph ∵ on pink (LisaTerminal → VT323). */
export function Glyph({ className = "" }: { className?: string }) {
  return <span className={`inline-flex items-center justify-center bg-pink font-pixel leading-none text-ink ${className}`}>∵</span>;
}
