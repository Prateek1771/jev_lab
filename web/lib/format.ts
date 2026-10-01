export const pct = (x: number | null | undefined, digits = 0) => (x == null ? "n/a" : `${(x * 100).toFixed(digits)}%`);

export function usd(x: number | null | undefined): string {
  if (x == null) return "n/a";
  if (x === 0) return "$0";
  if (x >= 0.01) return `$${x.toFixed(3)}`;
  return `$${x.toFixed(6)}`;
}

export const ms = (x: number | null | undefined) => (x == null ? "n/a" : x >= 1000 ? `${(x / 1000).toFixed(1)} s` : `${Math.round(x)} ms`);

export const num = (x: number | null | undefined, digits = 2) => (x == null ? "" : x.toFixed(digits));

/** The pill colour of a label: what the decision *does*, not what it is called. */
const RED = new Set(["block", "invalid", "injection", "pii", "flag", "reject", "contradicted", "investigate", "disqualify", "skip-secret", "leak", "(invalid)", "ERROR", "miss"]);
const BLUE = new Set(["confirm", "review", "asked_user", "nurture", "insufficient", "route_queue", "refund_confirm", "ask_user", "(human)", "human", "balanced"]);
const GREEN = new Set(["allow", "valid", "release", "store", "execute", "safe", "clean", "answer", "answered", "supported", "sales_now", "refund_auto", "urgent", "fast"]);
const ORANGE = new Set(["frontier", "high", "skip", "no_answer", "not_urgent", "medium"]);

export type Tone = "red" | "blue" | "green" | "orange" | "gray" | "magenta";

export function tone(label: string | null | undefined): Tone {
  if (!label) return "gray";
  if (RED.has(label)) return "red";
  if (BLUE.has(label)) return "blue";
  if (GREEN.has(label)) return "green";
  if (ORANGE.has(label)) return "orange";
  return "gray";
}

// Hex, not var(): SVG presentation attributes (recharts fills/strokes) don't resolve CSS variables reliably.
export const HEX = {
  magenta: "#d45bb6", teal: "#09aea1", orange: "#e8912d", violet: "#9b8cf5", sage: "#abbab9",
  green: "#03aa5c", blue: "#5b8def", red: "#e5484d", gray: "#7a7a7a",
  grid: "#333333", border: "#3a3a3a", label: "#bdbdbd", title: "#e6e6e6", panel: "#262626",
};

export const TONE_COLOR: Record<Tone, string> = {
  red: HEX.red, blue: HEX.blue, green: HEX.green, orange: HEX.orange, gray: HEX.gray, magenta: HEX.magenta,
};

/** Series colours from the reference charts: Jev magenta, model baselines teal/orange, free code sage. */
export function seriesColor(key: string, kind?: string): string {
  if (key === "jev") return HEX.magenta;
  if (kind === "free") return HEX.sage;
  if (/frontier|always_review|ladder/.test(key)) return HEX.orange;
  return HEX.teal;
}
