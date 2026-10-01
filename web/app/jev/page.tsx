import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, Label, MetaRow } from "@/components/ui";
import { AUTHOR } from "@/lib/site";

export const metadata: Metadata = {
  title: "What is Jev",
  alternates: { canonical: "/jev" },
  description: "Jev is TypeSafe AI's first System One model: typed decisions with calibrated probabilities instead of text. What it is, how it's called, where it's weak, and where to find it.",
};

// Every claim below is TypeSafe's, from typesafe.ai, its launch post and docs.typesafe.ai (checked 2026-09-26).
// The wire shapes are the ones this lab sends (shared/openrouter.py); the answer numbers are illustrative.

const VS: [string, string, string][] = [
  ["Trained for", "Human preference: write-ups and chat replies.", "Calibrated decisions: answers with honest probabilities (RLCD, Reinforcement Learning for Calibrated Decisions)."],
  ["Returns", "A string you parse and validate, and hope it isn't a hallucinated label.", "A typed value from the options you defined. TypeSafe: “the model never makes type errors.”"],
  ["Confidence", "None you can trust; ask it and it writes a number.", "Calibrated probabilities on every answer, so code can act, or escalate when unsure."],
  ["Speed", "3 to 329 seconds end to end on these tasks (TypeSafe's figures).", "70 to 500 ms end to end, which TypeSafe puts at 40–200× faster."],
  ["Price", "$0.20 to $10 per million input tokens; output ~5× more.", "$0.042 per million input tokens. Output tokens are free."],
];

const PRIMITIVES = [
  {
    name: "Choice",
    what: "Pick one of your options (up to 255). Comes back with a confidence and the probability of every option.",
    code: `"team": {
  "type": "choice",
  "instructions": "Which team handles this?",
  "criteria": {
    "billing": "Charges, refunds",
    "technical": "Bugs, outages",
    "other": "Anything else"
  }
}
→ {"choice": "billing",
   "confidence": 0.93,
   "probabilities": {...}}`,
  },
  {
    name: "Score",
    what: "Rate against an ordered rubric of 2 to 10 levels, lowest first. Returns the expected level, a confidence and each level's probability.",
    code: `"severity": {
  "type": "score",
  "instructions": "How severe is it?",
  "criteria": [
    "Cosmetic",
    "Some users hit",
    "Outage"
  ]
}
→ {"score": 1.8,
   "confidence": 0.81,
   "probabilities": {...}}`,
  },
  {
    name: "Noul",
    what: "How likely a statement is to be true, 0 to 1. No confidence field: the probability is the answer, and your code picks the threshold.",
    code: `"urgent": {
  "type": "noul",
  "instructions": "It is urgent.",
  "criteria": {
    "true": "Outage or deadline",
    "false": "No time pressure"
  }
}
→ {"noul": 0.97}`,
  },
];

const CALL = `import httpx

r = httpx.post(
    "https://openrouter.ai/api/alpha/decisions",
    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
    json={
        "model": "typesafe/jev-1.13",
        "state": {"ticket": "I was charged twice for order A-104."},
        "questions": {"team": {"type": "choice", ...}},   # as many as you like
    },
)
answer = r.json()["answers"]["team"]
if answer["confidence"] >= 0.8:
    route(answer["choice"])        # sure enough: act
else:
    send_to_human()                # not sure: escalate`;

// TypeSafe's own published list for jev-1.13 (docs.typesafe.ai/model-jaggedness/jev-1.13), first ten.
const JAGGED: [string, string][] = [
  ["Literal reading", "Answers the question you wrote, not the one you meant."],
  ["Math and numbers", "Struggles with counting and numeric precision."],
  ["Numeric representations", "Can't reliably judge how close two hex values or RGB triples are."],
  ["Math using score", "Score levels are a rubric, not a ruler: don't average or interpolate them."],
  ["Dates and times", "Reads dates as text, not as ordered quantities. Parse them in code first."],
  ["Indirection", "Double negatives and multi-hop reasoning cost accuracy."],
  ["Irrelevant state", "Unrelated detail in the state acts as a distractor."],
  ["Adversarial content", "Text written to steer the model can influence the answer."],
  ["Contradictory criteria", "Overlapping options or rubric levels give confident answers that mean little."],
  ["P(noul) + P(not noul) ≠ 1", "1 − noul is not the probability of the opposite statement."],
];

type Platform = { name: string; href: string; what: string };
const PLATFORMS: { group: string; note: string; items: Platform[] }[] = [
  {
    group: "TypeSafe AI",
    note: "official",
    items: [
      { name: "typesafe.ai", href: "https://typesafe.ai/", what: "The company behind Jev and System One models." },
      { name: "Launch post", href: "https://typesafe.ai/blog/introducing-system-one-models-and-jev", what: "Introducing System One models and Jev." },
      { name: "Docs", href: "https://docs.typesafe.ai/", what: "Quick start, primitives, patterns, ML primer." },
      { name: "Jaggedness report", href: "https://docs.typesafe.ai/model-jaggedness/jev-1.13", what: "Where jev-1.13 is weak, in TypeSafe's own words." },
      { name: "Console & playground", href: "https://console.typesafe.ai/", what: "Early-access API keys and a playground." },
      { name: "Evals", href: "https://evals.typesafe.ai/", what: "TypeSafe's published evaluations." },
      { name: "Python adapter", href: "https://github.com/typesafe-ai/system-one-adapter-python", what: "github.com/typesafe-ai: the official SDK." },
      { name: "X", href: "https://x.com/typesafeai", what: "@typesafeai: releases and announcements." },
      { name: "LinkedIn", href: "https://www.linkedin.com/company/typesafe-ai/", what: "TypeSafe AI's company page." },
    ],
  },
  {
    group: "OpenRouter",
    note: "how this lab calls it",
    items: [
      { name: "Jev 1.13 on OpenRouter", href: "https://openrouter.ai/typesafe/jev-1.13", what: "Model page, pricing and providers. One key for Jev and the baselines." },
      { name: "What is Jev?", href: "https://openrouter.ai/blog/insights/what-is-jev/", what: "OpenRouter's explainer for developers." },
    ],
  },
];

export default function WhatIsJev() {
  return (
    <div className="fade-in">
      <section className="pt-16 pb-10 text-center sm:pt-24">
        <div className="mb-8 flex justify-center">
          <MetaRow items={[
            { k: "made by", v: "TypeSafe AI" },
            { k: "model", v: "typesafe/jev-1.13" },
            { k: "launched", v: "15 Sep 2026 · early access" },
            { k: "price", v: "$0.042 / M input · output free" },
          ]} />
        </div>
        <h1 className="h-hero">What is Jev</h1>
        <p className="mx-auto mt-8 max-w-[780px] text-[19px] leading-[1.35] text-ink-86">
          Jev is TypeSafe AI&apos;s first <b className="text-ink">System One model</b>. It doesn&apos;t write text for people to read.
          It makes <b className="text-ink">decisions inside software</b>: you give it state and a typed question, it gives back
          one of the answers you allowed, with calibrated probabilities your code can branch on.
        </p>
        <p className="mx-auto mt-5 max-w-[780px] font-mono text-[12px] leading-[1.5] text-gray">
          Claims on this page are TypeSafe&apos;s own, linked below. Jev Lab is unofficial: tests by{" "}
          <a href={AUTHOR.url} target="_blank" rel="noreferrer" className="u text-ink">{AUTHOR.name}</a>, not affiliated with TypeSafe AI.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="h-section mb-8">System One, Not a Chatbot</h2>
        <div className="border-t-[1.2px] border-ink">
          <div className="hidden gap-6 rule-b py-2 md:grid md:grid-cols-[200px_1fr_1fr]">
            {["", "An LLM", "Jev"].map((h) => <Label key={h} className="text-gray">{h}</Label>)}
          </div>
          {VS.map(([k, llm, jev]) => (
            <div key={k} className="grid gap-2 rule-b py-5 md:grid-cols-[200px_1fr_1fr] md:gap-6">
              <Label className="pt-1">{k}</Label>
              <p className="text-[16px] leading-[1.35] text-ink-86"><span className="cap mr-2 text-gray md:hidden">LLM</span>{llm}</p>
              <p className="text-[16px] leading-[1.35] text-ink"><span className="cap mr-2 text-gray md:hidden">Jev</span><b className="font-medium">{jev}</b></p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-20">
        <h2 className="h-section mb-3">Three Questions It Can Answer</h2>
        <p className="mb-8 max-w-[70ch] text-[17px] leading-[1.35] text-ink-86">
          Every call asks one or more typed questions about the same state. They&apos;re answered in parallel, so adding
          questions barely adds time, and you can mix all three in one request.
        </p>
        <div className="grid gap-px border-[1.2px] border-ink bg-ink lg:grid-cols-3">
          {PRIMITIVES.map((p) => (
            <div key={p.name} className="flex flex-col gap-4 bg-page p-5">
              <div className="font-display text-[40px] leading-[0.9] font-medium tracking-[-0.02em] text-ink">{p.name}</div>
              <p className="min-h-[4.2em] text-[15px] leading-[1.4] text-ink-86">{p.what}</p>
              <CodeBlock>{p.code}</CodeBlock>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-20 grid gap-8 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 className="h-section mb-6">A Smart If-Statement</h2>
          <div className="space-y-4 text-[17px] leading-[1.4] text-ink-86">
            <p>TypeSafe&apos;s pitch is automation, not conversation: workflows with <b className="text-ink">smart if-statements</b>, map-reduce over big data, real-time apps, and score / judge / verify / guardrail steps.</p>
            <p>Ask <b className="text-ink">atomic questions</b>, one judgment each. Combine them in code, not in a prompt. Counting, facts and hard rules stay in code too.</p>
            <p>Then use the confidence: <b className="text-ink">act when it&apos;s high, escalate when it isn&apos;t</b>. That&apos;s the pattern every one of the 25 experiments here tests.</p>
          </div>
        </div>
        <div className="min-w-0">
          <Label className="mb-2 text-gray">the exact call this lab makes, via OpenRouter</Label>
          <CodeBlock>{CALL}</CodeBlock>
        </div>
      </section>

      <section className="mt-20">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <h2 className="h-section">Where It&apos;s Weak</h2>
          <a href="https://docs.typesafe.ai/model-jaggedness/jev-1.13" target="_blank" rel="noreferrer" className="u font-mono text-[12px] text-ink">TypeSafe&apos;s jaggedness report ↗</a>
        </div>
        <p className="mb-6 max-w-[70ch] text-[17px] leading-[1.35] text-ink-86">
          Unusually, TypeSafe publishes its model&apos;s weak spots. Design around these: parse numbers and dates in code,
          keep the state short, write criteria that don&apos;t overlap.
        </p>
        <div className="grid border-t-[1.2px] border-ink md:grid-cols-2 md:gap-x-10">
          {JAGGED.map(([k, v]) => (
            <div key={k} className="grid gap-1 rule-b py-4 sm:grid-cols-[220px_1fr] sm:gap-4">
              <Label className="pt-0.5">{k}</Label>
              <p className="text-[15px] leading-[1.4] text-ink-86">{v}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 text-[17px] text-ink-86">
          How it holds up on real work: <Link href="/#projects" className="u text-ink">the 25 experiments, measured →</Link>
        </p>
      </section>

      <section id="platforms" className="mt-20 scroll-mt-16">
        <h2 className="h-section mb-3">Where to Find Jev</h2>
        <p className="mb-8 max-w-[70ch] text-[17px] leading-[1.35] text-ink-86">
          Official channels only. Look-alike sites and community orgs using the name aren&apos;t TypeSafe&apos;s and aren&apos;t listed.
        </p>
        <div className="space-y-10">
          {PLATFORMS.map((g) => (
            <div key={g.group}>
              <Label className="mb-3">{g.group} <span className="text-gray">· {g.note}</span></Label>
              <div className={`grid gap-px border-[1.2px] border-ink bg-ink sm:grid-cols-2 ${g.items.length % 3 ? "" : "lg:grid-cols-3"}`}>
                {g.items.map((p) => (
                  <a key={p.href} href={p.href} target="_blank" rel="noreferrer"
                    className="group flex min-w-0 flex-col gap-2 bg-page p-5 transition-colors duration-500 ease-house hover:bg-ink hover:text-paper">
                    <span className="flex items-start justify-between gap-3">
                      <span className="text-[20px] leading-[1.15] font-medium">{p.name}</span>
                      <span className="text-[18px] transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden>↗</span>
                    </span>
                    <span className="text-[14px] leading-[1.4] opacity-85">{p.what}</span>
                    <span className="mt-auto truncate pt-2 font-mono text-[11px] tracking-[0.04em] opacity-60">{p.href.replace(/^https:\/\/(www\.)?/, "").replace(/\/$/, "")}</span>
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
