// Mirrors api/main.py and core/run.py. The API is the only source of numbers.

export type RunJson = {
  variant: string;
  title: string;
  model: string;
  label: string | null;
  outcome: string;
  confidence: number | null;
  probability: number | null;
  score: number | null;
  quality: number | null;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
  raw: Record<string, unknown>;
};

export type ResultJson = { runs: RunJson[]; trace_url: string | null };

export type Headline = {
  title: string;
  kind: "jev" | "llm" | "free";
  accuracy: number | null;
  correct: number;
  done: number;
  pass_rate: number | null;
  passed: number;
  graded: number;
  total_cost: number;
  cost_per_pass: number | null;
  p50_ms: number | null;
};

export type RunMeta = {
  file: string;
  label: string;
  date: string;
  rows: number;
  errors: number;
  spend: number;
  headline: Record<string, Headline>;
};

export type SweepSpec = { positive: string; value: "probability" | "score" };
export type SafetySpec = { unsafe: string; safe: string; names?: string[] };

export type ProjectSummary = {
  id: string;
  title: string;
  name: string;
  primitive: string;
  labels: string[];
  examples: string[];
  rows: number;
  traced: boolean;
  sweep: SweepSpec | null;
  safety: SafetySpec | null;
  players: string[] | null;   // a live game (25: chess): the Play tab's player list
  latest: RunMeta | null;
};

export type ProjectDetail = Omit<ProjectSummary, "examples"> & {
  description: string;
  examples: Record<string, string | Record<string, unknown>>;
  diagrams: { heading: string; mermaid: string }[];
};

export type VariantSummary = {
  rows: number;
  errors: number;
  accuracy: number | null;
  correct: number;
  invalid: number;
  p50_ms: number | null;
  p95_ms: number | null;
  total_cost: number;
  cost_missing: number;
  labels: Record<string, number>;
  graded: number;
  passed: number;
  pass_rate: number | null;
  cost_per_pass: number | null;
  safety?: {
    unsafe: number;
    unsafe_blocked: number;
    unsafe_allowed: number;
    block_rate: number | null;
    safe: number;
    safe_stopped: number;
    false_positive_rate: number | null;
  };
  [raw: string]: unknown;
};

export type SweepPoint = { threshold: number; tp: number; fp: number; fn: number; tn: number; accuracy: number | null; cost?: number };

export type Report = {
  variants: { key: string; title: string }[];
  summary: Record<string, VariantSummary>;
  label_keys: string[];
  wrong: { idx: number; expected: string; text: string; error: string | null; jev_value: number | null; got: Record<string, string> }[];
  safety_names: string[] | null;
  raw_metrics: { key: string; label: string; pct: boolean }[];
  sweep: (SweepSpec & { points: SweepPoint[]; best: SweepPoint; cost_fn: number; cost_fp: number }) | null;
};

export type SavedRow = ResultJson & { idx: number; text: string; expected: string; input: unknown; error: string | null };

export type Diff = {
  variants: {
    key: string;
    title: string;
    before: { correct: number; rows: number; passed: number; graded: number; cost: number };
    after: { correct: number; rows: number; passed: number; graded: number; cost: number };
  }[];
  changed: { idx: number; variant: string; text: string; expected: string; before: string | null; after: string | null; q_before: number | null; q_after: number | null }[];
};
