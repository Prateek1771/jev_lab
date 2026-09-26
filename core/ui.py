"""Shared Streamlit rendering. Reads Result/Run only; never imports a project's backend.
The numbers themselves live in core/report.py (pure), shared with the web API."""

from pathlib import Path

import pandas as pd
import streamlit as st

from core.report import (PASS, RAW_METRICS, RAW_PCT, SAFETY_NAMES, TITLES, cheapest, fmt_cost,  # noqa: F401
                         handed_off, jev_value, outcome, parse_about, safety, summarize, sweep, sweep_grid, title,
                         variants)
from core.run import Result, Run


def _2dp(x: float | None) -> str:
    return "" if x is None else f"{x:.2f}"


def md_text(text: str) -> str:
    """Model text shown as markdown: Streamlit renders $...$ as LaTeX, so "$120 plus $7.50" came out as garbled
    italic math (found in the re-test, 24's frontier answer). Escape the dollars; everything else stays markdown."""
    return text.replace("$", r"\$")


def render_run(run: Run) -> None:
    st.subheader(title(run.variant))
    st.caption(run.model)
    if run.valid:
        st.metric("Label", run.label)
    elif handed_off(run):
        st.info("Sent to a human: no automatic decision")
    else:
        st.error("Answer outside the schema")
    # float(): JSON may send 1 as an int, and st.progress reads ints as 0-100 percent.
    if run.confidence is not None:
        st.progress(float(run.confidence), text=f"confidence {run.confidence:.2f}")
    if run.probability is not None:
        st.progress(float(run.probability), text=f"P({run.raw.get('p_of', 'yes')}) {run.probability:.2f}")
    if run.score is not None:
        top = run.raw.get("levels", 3) - 1
        st.progress(min(float(run.score) / top, 1.0), text=f"score {run.score:.2f} of {top}")
    if run.quality is not None:   # graded free-text answers (05+)
        st.progress(float(run.quality), text=f"grader: P(correct) {run.quality:.2f} ({'pass' if run.quality >= PASS else 'fail'})")
    if run.raw.get("finish_reason") == "length":   # graded answers (05+): the grade can't be fair to it
        st.warning("Answer cut off at the token cap (finish_reason = length): its grade is unreliable.")
    if run.raw.get("answer"):   # routed to a human (18): no answer to show
        with st.expander("Answer"):
            st.markdown(md_text(run.raw["answer"]))
    if "steps" in run.raw:   # agent loops (06+): every tool call, in order, then how it stopped
        st.code("\n".join([f"{i}. {s['tool']}({s['args']})" + "".join(f" [{s[k]}]" for k in ("gate", "filtered") if k in s)
                           + f" -> {s['result']}" for i, s in enumerate(run.raw["steps"], 1)]   # gate, filter: 24
                          + [f"stop: {run.raw['stop']}"]), language=None, wrap_lines=True)
    if "redacted" in run.raw:   # PII (12+): what the LLM would receive after masking
        st.caption("What the LLM receives:")
        st.code(run.raw["redacted"], language=None, wrap_lines=True)
    if "claims" in run.raw:   # citation checks (10+): each sentence, its verdict, and what each cited source said
        st.code("\n".join(f"{i}. {c['verdict']:<12} {c['text']}\n   "
                          + (c["code"] or " · ".join(f"[{x['source']}] {x['choice']} {x['confidence']:.2f}" for x in c["checks"]))
                          for i, c in enumerate(run.raw["claims"], 1)), language=None, wrap_lines=True)
    if "actions" in run.raw:   # projects that act on a decision (04+)
        st.caption(f"band **{run.raw['band']}** · {md_text(run.raw['reason'])}")
        st.code("\n".join(run.raw["actions"]), language=None)
    elif "reason" in run.raw:   # a decision with no actions, e.g. 05's model tier
        st.caption(md_text(run.raw["reason"]))
    with st.expander("Raw"):
        st.json(run.raw)


def render_metrics(result: Result) -> None:
    runs = list(result.runs.values())
    st.divider()
    st.subheader("Experiment metrics")
    rows = {
        "Latency (ms)": [round(r.latency_ms) for r in runs],
        "Input tokens": [r.input_tokens for r in runs],
        "Output tokens": [r.output_tokens for r in runs],
        "Cost (USD)": [fmt_cost(r.cost_usd) for r in runs],
        "Valid label": [r.valid for r in runs],
        "Confidence": [_2dp(r.confidence) for r in runs],
        "P(yes)": [_2dp(r.probability) for r in runs],
        "Score": [_2dp(r.score) for r in runs],
        "Quality": [_2dp(r.quality) for r in runs],
    }
    rows = {k: v for k, v in rows.items() if any(x not in (None, "") for x in v)}   # hide rows no variant reports
    st.table(pd.DataFrame(rows, index=[title(r.variant) for r in runs]).T.astype(str))

    names = [title(r.variant) for r in runs]
    c1, c2 = st.columns(2)
    c1.caption("Latency (ms)")
    c1.bar_chart(pd.DataFrame({"ms": [r.latency_ms for r in runs]}, index=names))
    if all(r.cost_usd is not None for r in runs):
        c2.caption("Cost (USD)")
        c2.bar_chart(pd.DataFrame({"usd": [r.cost_usd for r in runs]}, index=names))

    if result.trace_url:   # only projects that trace (multi-step agents, 06+) set this
        st.link_button("Open trace in Langfuse", result.trace_url)


def render_about(path: Path) -> None:
    """The description, then each diagram full width (With Jev, then Without Jev). Missing file: nothing.
    Full width, not side by side: left-to-right flowcharts shrink to unreadable text in half a page."""
    if not path.exists():
        return
    description, diagrams = parse_about(path.read_text(encoding="utf-8"))
    st.markdown(description)
    if diagrams:
        with st.expander("How it's wired: with Jev vs without Jev", expanded=True):
            for heading, body in diagrams:
                st.markdown(f"**{heading}**")
                st.mermaid_chart(body)


def render_result(result: Result) -> None:
    for col, run in zip(st.columns(len(result.runs)), result.runs.values()):
        with col:
            render_run(run)
    render_metrics(result)


def render_batch(rows: list[dict], labels: list[str], sweep_spec: dict | None = None, key: str = "",
                 safety_spec: dict | None = None) -> None:
    st.divider()
    st.subheader(f"Dataset run — {len(rows)} labeled examples")
    names = variants(rows)
    s = {v: summarize(rows, v) for v in names}

    def fmt(v, kind):
        if v is None:
            return "n/a"
        return {"pct": f"{v:.0%}", "ms": f"{v:.0f}", "usd": f"${v:.6f}", "2dp": f"{v:.2f}"}.get(kind, str(v))

    table = {
        "Accuracy": [fmt(s[v]["accuracy"], "pct") for v in names],
        "Correct": [f'{s[v]["correct"]}/{s[v]["rows"] - s[v]["errors"]}' for v in names],
        "Invalid answers": [s[v]["invalid"] for v in names],
        "p50 latency (ms)": [fmt(s[v]["p50_ms"], "ms") for v in names],
        "p95 latency (ms)": [fmt(s[v]["p95_ms"], "ms") for v in names],
        "Total cost (USD)": [fmt(s[v]["total_cost"], "usd") for v in names],
        "Rows missing cost": [s[v]["cost_missing"] for v in names],
    }
    if any(s[v]["graded"] for v in names):   # graded projects (05+)
        table["Answers passing grader"] = [f'{s[v]["passed"]}/{s[v]["graded"]}' for v in names]
        table["Pass rate"] = [fmt(s[v]["pass_rate"], "pct") for v in names]
        table["Cost per passing answer"] = [fmt(s[v]["cost_per_pass"], "usd") for v in names]
    for key, label in RAW_METRICS.items():   # RAG (08+): only the rows some variant reports
        if any(s[v][key] is not None for v in names):
            table[label] = [fmt(s[v][key], "pct" if key in RAW_PCT else "2dp") for v in names]
    if safety_spec:   # gates (07+)
        g = {v: safety(rows, v, safety_spec["unsafe"], safety_spec["safe"]) for v in names}
        caught, allowed, stopped = safety_spec.get("names", SAFETY_NAMES)   # 10 renames them for citations
        table[caught] = [f'{g[v]["unsafe_blocked"]}/{g[v]["unsafe"]} ({fmt(g[v]["block_rate"], "pct")})' for v in names]
        table[allowed] = [g[v]["unsafe_allowed"] for v in names]
        table[stopped] = [f'{g[v]["safe_stopped"]}/{g[v]["safe"]} ({fmt(g[v]["false_positive_rate"], "pct")})' for v in names]
    st.table(pd.DataFrame(table, index=[title(v) for v in names]).T.astype(str))
    errors = sum(r["result"] is None for r in rows)
    if errors:
        st.warning(f"{errors} row(s) failed and are excluded from every number above.")
    n = len(rows) - errors
    if n:
        st.caption(f"With {n} examples, one example is {1 / n:.0%} of accuracy. Differences of a row or two are noise.")

    st.caption("Label counts: a label that never appears means the model never picked it, or your code can't produce it.")
    extra = ["(human)"] if any(s[v]["labels"].get("(human)") for v in names) else []   # escalation (17+)
    keys = [*labels, *extra, "(invalid)"]   # so each column sums to the completed rows
    st.table(pd.DataFrame({title(v): [s[v]["labels"].get(k, 0) for k in keys] for v in names}, index=keys))

    wrong = [r for r in rows if r["result"] is None
             or any(run.label != r["expected"] for run in r["result"].runs.values())]
    st.caption(f"{len(wrong)} row(s) where at least one variant was wrong or the row failed:")
    st.dataframe(pd.DataFrame([{
        "expected": r["expected"],
        **{v: (outcome(r["result"].runs[v]) if r["result"] else "ERROR") for v in names},
        "jev value": jev_value(r),
        "text": r["text"],
        "error": r["error"],
    } for r in wrong]))

    if sweep_spec:
        render_sweep(rows, sweep_spec, key)


def render_sweep(rows: list[dict], spec: dict, key: str) -> None:
    st.divider()
    st.subheader("Threshold sweep (from this run's stored values — no API calls)")
    value, positive = spec["value"], spec["positive"]
    grid = sweep_grid(rows, value)
    c1, c2 = st.columns(2)
    cost_fn = c1.number_input(f"Cost of a missed '{positive}'", min_value=0.0, value=5.0, key=f"fn-{key}")
    cost_fp = c2.number_input(f"Cost of a false '{positive}' alarm", min_value=0.0, value=1.0, key=f"fp-{key}")
    points = sweep(rows, positive, value, grid)
    best = cheapest(points, cost_fn, cost_fp)
    st.success(f"Cheapest threshold on these rows: **{value} ≥ {best['threshold']}** "
               f"(missed {best['fn']}, false alarms {best['fp']}, accuracy {best['accuracy']:.0%}).")
    df = pd.DataFrame(points).set_index("threshold")
    st.line_chart(df[["fn", "fp", "cost"]])
    st.dataframe(df)
    st.caption("This threshold was picked on the same rows it is scored on, so its accuracy is optimistic. "
               "Confirm it on rows the sweep never saw before you trust it.")
