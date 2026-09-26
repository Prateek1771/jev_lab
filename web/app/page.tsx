import Link from "next/link";
import { OverviewChart } from "@/components/OverviewChart";
import type { ScatterPoint } from "@/components/charts";
import { MobilePager } from "@/components/MobilePager";
import { Glyph, Label, MetaRow, Panel } from "@/components/ui";
import { getProjects } from "@/lib/api";
import { AUTHOR } from "@/lib/site";
import { pct, usd } from "@/lib/format";
import type { Headline, ProjectSummary } from "@/lib/types";

const score = (h: Headline) => (h.graded ? h.pass_rate : h.accuracy) ?? 0;
const perDecision = (h: Headline) => (h.done ? h.total_cost / h.done : 0);

function best(p: ProjectSummary, kind: "llm" | "free") {
  const hs = Object.entries(p.latest?.headline ?? {}).filter(([, h]) => h.kind === kind);
  return hs.sort(([, a], [, b]) => score(b) - score(a) || perDecision(a) - perDecision(b))[0];
}

function median(xs: number[]) {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
}

export default async function Overview() {
  const projects = await getProjects();
  const withRuns = projects.filter((p) => p.latest);
  const points: ScatterPoint[] = withRuns.flatMap((p) =>
    Object.entries(p.latest!.headline).map(([variant, h]) => ({
      project: p.id, name: p.name, variant, title: h.title, kind: h.kind, cost: perDecision(h), acc: score(h), graded: h.graded > 0,
    })),
  );
  const rows = withRuns.map((p) => ({ p, jev: p.latest!.headline.jev, llm: best(p, "llm"), free: best(p, "free") }));
  const ties = rows.filter((r) => r.jev && r.llm && score(r.jev) >= score(r.llm[1])).length;
  const freeLoses = rows.filter((r) => r.free && r.jev && score(r.free[1]) < score(r.jev)).length;
  const freeCount = rows.filter((r) => r.free).length;
  const ratio = median(rows.filter((r) => r.jev && r.llm && perDecision(r.jev) > 0).map((r) => perDecision(r.llm![1]) / perDecision(r.jev)));
  const labeled = projects.reduce((n, p) => n + p.rows, 0);

  return (
    <div className="fade-in">
      <section className="pt-16 pb-10 text-center sm:pt-24">
        <div className="mb-8 flex justify-center">
          <MetaRow
            items={[
              { k: "experiments", v: projects.length },
              { k: "labeled rows", v: labeled },
              { k: "decision model", v: "typesafe/jev-1.13 via OpenRouter" },
              { k: "every number", v: "from a real run" },
            ]}
          />
        </div>
        <h1 className="h-hero">Jev Lab</h1>
        <p className="mx-auto mt-8 max-w-[780px] text-[19px] leading-[1.35] text-ink-86">
          Twenty-four decisions an AI product makes every day: classify, gate, route, filter, verify.
          Each one decided three ways: by <b className="text-ink">Jev</b>, by an <b className="text-ink">LLM</b>, and by <b className="text-ink">plain code</b>.
          Same rows, real API calls, every mistake counted.
        </p>
        <p className="mt-5 text-[17px]">
          <Link href="/jev" className="u text-ink">New to Jev? What it is and where to find it →</Link>
        </p>
        <p className="mx-auto mt-5 max-w-[780px] font-mono text-[12px] leading-[1.5] text-gray">
          Unofficial tests by <a href={AUTHOR.url} target="_blank" rel="noreferrer" className="u text-ink">{AUTHOR.name}</a>, not affiliated with TypeSafe AI.
          Run with his own OpenRouter API key; OpenRouter is the provider for the Jev model.
        </p>
      </section>

      <section className="grid gap-px border-[1.2px] border-ink bg-ink md:grid-cols-3">
        {[
          { big: `${ties}/${rows.length}`, small: "projects where Jev is as accurate as the best LLM baseline, or better" },
          { big: `${ratio.toFixed(1)}×`, small: "median: an LLM decision costs this many Jev decisions" },
          { big: `${freeLoses}/${freeCount}`, small: "no-model baselines (rules, regex, lists) that Jev beats on the same rows" },
        ].map((s) => (
          <div key={s.small} className="bg-page px-5 py-6">
            <div className="font-display text-[56px] leading-[0.9] font-medium tracking-[-0.02em] text-ink">{s.big}</div>
            <div className="mt-3 max-w-[34ch] text-[15px] text-ink-86">{s.small}</div>
          </div>
        ))}
      </section>

      <section className="mt-10">
        <Panel title="Every experiment: accuracy vs cost" hint="latest saved run of each project; click a point to open it">
          <OverviewChart points={points} />
          <p className="mt-2 font-mono text-[11px] text-viz-label">
            Graded projects plot pass rate; the rest plot accuracy against the labels. No-model baselines cost $0 and sit in the “free” column.
          </p>
        </Panel>
      </section>

      <section id="projects" className="mt-20 scroll-mt-16">
        <div className="mb-6 flex items-end justify-between gap-6">
          <h2 className="h-section">The 24 Experiments</h2>
          <Label className="hidden text-right md:block">score · cost per decision</Label>
        </div>
        <div className="border-t-[1.2px] border-ink">
          <div className="hidden grid-cols-[64px_minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_28px] gap-4 rule-b py-2 md:grid">
            {["#", "experiment", "Jev", "best LLM baseline", "no-model baseline", ""].map((h) => <Label key={h} className="text-gray">{h}</Label>)}
          </div>
          <MobilePager size={6} noun="experiments">
          {projects.map((p) => {
            const r = rows.find((x) => x.p.id === p.id);
            const cell = (label: string, h?: Headline, name?: string) =>
              h ? (
                <div>
                  <Label className="mb-0.5 text-gray md:hidden">{label}</Label>
                  <div className="text-[17px] font-medium text-ink">{pct(score(h))}<span className="ml-2 font-mono text-[12px] font-normal text-gray">{usd(perDecision(h))}</span></div>
                  {name && <div className="truncate font-mono text-[11px] text-gray">{h.title}</div>}
                </div>
              ) : <span className="font-mono text-[12px] text-gray"><span className="md:hidden">{label}: </span>—</span>;
            return (
              <Link key={p.id} href={`/p/${p.id}`}
                className="group grid grid-cols-[48px_1fr] gap-x-4 gap-y-2 rule-b py-4 transition-colors duration-200 ease-house hover:bg-paper/40 md:grid-cols-[64px_minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_28px] md:items-center">
                <span className="font-pixel text-[30px] leading-none text-ink">{p.id}</span>
                <div>
                  <div className="h3 group-hover:underline group-hover:decoration-[1.2px] group-hover:underline-offset-4">{p.name}</div>
                  <div className="mt-1 font-mono text-[11px] tracking-[0.04em] text-gray">{p.primitive}</div>
                </div>
                <div className="col-start-2 md:col-start-auto">{cell("Jev", r?.jev)}</div>
                <div className="col-start-2 md:col-start-auto">{cell("best LLM", r?.llm?.[1], "x")}</div>
                <div className="col-start-2 md:col-start-auto">{cell("no model", r?.free?.[1], "x")}</div>
                <span className="hidden text-right text-[20px] text-ink transition-transform duration-200 group-hover:translate-x-1 md:block">→</span>
              </Link>
            );
          })}
          </MobilePager>
        </div>
      </section>

      <section id="method" className="mt-20 scroll-mt-16">
        <h2 className="h-section mb-8">How Each Experiment Is Run</h2>
        <div className="border-t-[1.2px] border-ink">
          {[
            ["Jev", "One decision call, typed.", "A Choice, a Noul (yes/no) or a Score, with calibrated probabilities. Code turns the answer into the action, so counting, facts and hard rules are never asked of a model."],
            ["LLM baseline", "The same question, as a prompt.", "The fast model with a plain or structured-output prompt, given the same policy and inputs. Where it matters, a frontier model too."],
            ["No-model baseline", "What you would write without AI.", "Regex, deny-lists, keyword filters, points tables, “store everything”. Free, and blind to meaning. Every dataset has rows written to test exactly that."],
            ["Measured", "Against labels, on real calls.", "Accuracy or a graded pass rate, unsafe actions allowed, cost per passing answer, latency. Saved runs live in History; the re-test diffs them row by row."],
          ].map(([k, claim, detail]) => (
            <div key={k} className="grid gap-2 rule-b py-5 md:grid-cols-[240px_1fr]">
              <Label className="pt-1">{k}</Label>
              <p className="text-[17px] leading-[1.35]"><b className="font-medium text-ink">{claim}</b> {detail}</p>
            </div>
          ))}
        </div>
        <div className="mt-6 flex items-center gap-3 font-mono text-[12px] text-gray">
          <Glyph className="h-5 w-5 text-[18px]" /> Streamlit still runs alongside: <code>uv run streamlit run app.py</code>
        </div>
      </section>
    </div>
  );
}
