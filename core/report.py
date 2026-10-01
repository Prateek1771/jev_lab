"""Pure numbers for a run or a batch of runs: no Streamlit, no web. Both UIs (core/ui.py, api/) and the test
reports use these, so every surface shows the same numbers."""

import dataclasses
import json
import re
import statistics
from collections import Counter

from core.run import Result, Run

TITLES = {"jev": "Jev-enhanced", "baseline": "Baseline: plain prompt", "structured": "Baseline: structured output",
          "llm_router": "LLM routes to a model", "frontier": "Always frontier",
          "llm_selector": "LLM picks the tool (same loop)", "tool_calling": "LLM native tool calling",
          "llm_filter": "LLM filters the chunks", "all_chunks": "Plain RAG: all chunks",
          "llm_rank": "LLM ranks the chunks", "retriever_order": "Retriever order (no rerank)",
          "llm_judge": "LLM judges the whole answer", "trust_citations": "Trust the citations",
          "pattern_filter": "Pattern deny-list (no model)",
          "regex": "Regex detectors only (no model)",
          "no_gate": "No gate: every reply ships", "llm_gate": "LLM judges the reply",
          "permission_list": "Permission allow/deny list (no model)",
          "static_checks": "Static checks, semgrep-style (no model)", "llm_reviewer": "LLM reviews the diff",
          "llm_agent_router": "LLM routes agent + tool (one call)", "flat_agent": "One flat agent, all 12 tools",
          "llm_self_confidence": "LLM's own confidence, same bands", "always_review": "Frontier reviews every action",
          "single_agent": "One LLM agent: triage + answer", "points": "Points-based lead scoring (no model)",
          "ladder": "Jev screens, frontier only above low", "rules_engine": "Rules engine (no model)",
          "frontier_all": "Frontier on every transaction", "keyword_filter": "Keyword filter (grep)",
          "everything": "Send the whole output", "llm_summary": "LLM summarizes first",
          "store_everything": "Store every message", "store_all": "Store every extracted edge",
          "llm_self_check": "LLM checks its own extraction",
          "plain_agent": "Plain agent: fast LLM + tools", "frontier_agent": "Frontier agent + tools",
          "cheap_llm": "Cheap OpenAI model (gpt-4.1-nano)", "heuristic": "Top tag score (no model)"}
PASS = 0.5   # a graded answer passes when the grader's P(correct) is at least this
# Per-row numbers a project stores in Run.raw; the batch view averages each one where it is defined (08+).
RAW_METRICS = {"precision": "Retrieval precision", "recall": "Retrieval recall", "ndcg": "nDCG@3", "mrr": "MRR",
               "rule_precision": "Rule precision", "rule_recall": "Rule recall", "tool_accuracy": "Agent + tool right",
               "reviewed": "Sent to review", "human": "Sent to a human", "frontier": "Sent to the frontier model",
               "context_tokens": "Tokens given to the answer",
               "unsafe": "Rows where a forbidden call RAN"}
RAW_PCT = {"precision", "recall", "rule_precision", "rule_recall", "tool_accuracy", "reviewed", "human", "frontier",
           "unsafe"}
SAFETY_NAMES = ["Unsafe calls blocked", "Unsafe calls ALLOWED", "Safe calls stopped"]


def title(variant: str) -> str:
    return TITLES.get(variant, variant)


def fmt_cost(c: float | None) -> str:
    return "n/a" if c is None else f"${c:.6f}"


def handed_off(run: Run) -> bool:
    """Escalation (17+): no automatic decision on purpose. Not an answer outside the schema."""
    return run.label is None and run.raw.get("route") == "human"


def outcome(run: Run) -> str:
    return run.label or ("(human)" if handed_off(run) else "(invalid)")


_DIAGRAM = re.compile(r"^## (.+?)\n+```mermaid\n(.*?)```", re.S | re.M)


def parse_about(text: str) -> tuple[str, list[tuple[str, str]]]:
    """A project's about.md: description, then "## <title>" + one mermaid block per diagram."""
    first = text.find("\n## ")
    return (text if first < 0 else text[:first]).strip(), [(t.strip(), body) for t, body in _DIAGRAM.findall(text)]


# --- Batch runs: one row per labeled example -------------------------------------------
# A row is {"text", "expected", "result": Result | None, "error": str | None}.


def _pct(xs: list[float], q: int) -> float | None:
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    return statistics.quantiles(xs, n=100, method="inclusive")[q - 1]


def variants(rows: list[dict]) -> list[str]:
    return next((list(r["result"].runs) for r in rows if r["result"] is not None), [])


def safety(rows: list[dict], variant: str, unsafe: str, safe: str) -> dict:
    """Gate numbers (07+). "Unsafe allowed" is the one that must be 0; "safe stopped" is the false-positive
    rate, the cost of a gate so cautious nobody can get work done. None when no such rows."""
    done = [r for r in rows if r["result"] is not None]
    bad = [r["result"].runs[variant].label for r in done if r["expected"] == unsafe]
    good = [r["result"].runs[variant].label for r in done if r["expected"] == safe]
    return {"unsafe": len(bad), "unsafe_blocked": bad.count(unsafe), "unsafe_allowed": bad.count(safe),
            "block_rate": bad.count(unsafe) / len(bad) if bad else None,
            "safe": len(good), "safe_stopped": sum(label != safe for label in good),
            "false_positive_rate": sum(label != safe for label in good) / len(good) if good else None}


def summarize(rows: list[dict], variant: str) -> dict:
    """Accuracy and cost for one variant over a batch."""
    done = [r for r in rows if r["result"] is not None]
    runs = [r["result"].runs[variant] for r in done]
    correct = sum(run.label == r["expected"] for run, r in zip(runs, done))
    lat = [run.latency_ms for run in runs]
    costs = [run.cost_usd for run in runs]
    total = sum(c for c in costs if c is not None)
    graded = [run for run in runs if run.quality is not None]
    passed = sum(run.quality >= PASS for run in graded)

    def mean(key):   # RAW_METRICS: average over the rows where the value exists, never counting None as 0
        xs = [run.raw[key] for run in runs if run.raw.get(key) is not None]
        return sum(xs) / len(xs) if xs else None
    return {
        "rows": len(rows),
        "errors": len(rows) - len(done),
        "accuracy": correct / len(done) if done else None,   # invalid answers count as wrong
        "correct": correct,
        "invalid": sum(not run.valid and not handed_off(run) for run in runs),
        "p50_ms": _pct(lat, 50),
        "p95_ms": _pct(lat, 95),
        "total_cost": total,
        "cost_missing": sum(c is None for c in costs),      # never silently treated as $0
        "labels": Counter(outcome(run) for run in runs),     # a label that never appears is a finding
        "graded": len(graded),
        "passed": passed,
        "pass_rate": passed / len(graded) if graded else None,
        "cost_per_pass": total / passed if passed else None,  # what one good answer really costs
        **{key: mean(key) for key in RAW_METRICS},   # e.g. precision/recall (08), nDCG/MRR (09)
    }


def jev_value(row: dict) -> float | None:
    if row["result"] is None or "jev" not in row["result"].runs:
        return None
    j = row["result"].runs["jev"]
    return next((x for x in (j.probability, j.score, j.confidence) if x is not None), None)


# --- Threshold sweep: re-decide stored Jev values offline. Zero API calls. ---------------


def sweep(rows: list[dict], positive: str, value: str, thresholds: list[float]) -> list[dict]:
    """For each threshold t: predict positive when Jev's `value` >= t, and count against the labels."""
    points = [(getattr(r["result"].runs["jev"], value), r["expected"] == positive)
              for r in rows if r["result"] is not None and getattr(r["result"].runs["jev"], value) is not None]
    out = []
    for t in thresholds:
        tp = sum(v >= t and pos for v, pos in points)
        fp = sum(v >= t and not pos for v, pos in points)
        fn = sum(v < t and pos for v, pos in points)
        tn = len(points) - tp - fp - fn
        out.append({"threshold": t, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                    "accuracy": (tp + tn) / len(points) if points else None})
    return out


def cheapest(points: list[dict], cost_fn: float, cost_fp: float) -> dict:
    """Lowest total mistake cost; ties go to higher accuracy, then the lower threshold."""
    for p in points:
        p["cost"] = cost_fn * p["fn"] + cost_fp * p["fp"]
    return min(points, key=lambda p: (p["cost"], -(p["accuracy"] or 0), p["threshold"]))


def sweep_grid(rows: list[dict], value: str) -> list[float]:
    if value == "probability":
        return [i / 20 for i in range(21)]
    top = next(r["result"].runs["jev"].raw.get("levels", 3) for r in rows if r["result"]) - 1   # score: 0..levels-1
    return [round(i / 10, 1) for i in range(top * 10 + 1)]


# --- Saved runs and JSON reports (the web UI) ------------------------------------------------


def row_from_saved(saved: dict) -> dict:
    """A saved row (dataset_real.py / the API's format: runs as dicts) → a batch row with a Result."""
    runs = saved.get("runs")
    return {"idx": saved.get("idx"), "text": saved["text"], "expected": saved["expected"], "error": saved.get("error"),
            "result": Result({v: Run(**d) for v, d in runs.items()}, trace_url=saved.get("trace_url")) if runs else None}


def row_to_saved(idx: int, item: dict, result: Result | None, error: str | None) -> dict:
    return {"idx": idx, "text": item["text"], "expected": item["label"], "note": item.get("note"),
            "input": item.get("input", item["text"]), "error": error,
            "runs": {v: dataclasses.asdict(r) for v, r in result.runs.items()} if result else None,
            "trace_url": result.trace_url if result else None}


def report(rows: list[dict], labels: list[str], safety_spec: dict | None = None,
           sweep_spec: dict | None = None, cost_fn: float = 5.0, cost_fp: float = 1.0) -> dict:
    """Everything the batch view shows, as plain JSON: per-variant summary, gate rows, label counts,
    wrong rows and the sweep. The same numbers core/ui.render_batch shows."""
    names = variants(rows)
    summary = {}
    for v in names:
        s = summarize(rows, v)
        s["labels"] = dict(s["labels"])
        if safety_spec:
            s["safety"] = safety(rows, v, safety_spec["unsafe"], safety_spec["safe"])
        summary[v] = s
    extra = ["(human)"] if any(summary[v]["labels"].get("(human)") for v in names) else []
    wrong = [{"idx": r.get("idx", i), "expected": r["expected"], "text": r["text"], "error": r["error"], "jev_value": jev_value(r),
              "got": {v: (outcome(r["result"].runs[v]) if r["result"] else "ERROR") for v in names}}
             for i, r in enumerate(rows)
             if r["result"] is None or any(run.label != r["expected"] for run in r["result"].runs.values())]
    out = {"variants": [{"key": v, "title": title(v)} for v in names], "summary": summary,
           "label_keys": [*labels, *extra, "(invalid)"], "wrong": wrong,
           "safety_names": (safety_spec or {}).get("names", SAFETY_NAMES) if safety_spec else None,
           "raw_metrics": [{"key": k, "label": lab, "pct": k in RAW_PCT} for k, lab in RAW_METRICS.items()
                           if any(summary[v][k] is not None for v in names)], "sweep": None}
    if sweep_spec and names and "jev" in names:
        points = sweep(rows, sweep_spec["positive"], sweep_spec["value"], sweep_grid(rows, sweep_spec["value"]))
        if points:
            out["sweep"] = {**sweep_spec, "points": points, "best": dict(cheapest(points, cost_fn, cost_fp)),
                            "cost_fn": cost_fn, "cost_fp": cost_fp}
    return out


def diff_runs(old: list[dict], new: list[dict]) -> dict:
    """Two saved runs of one project (saved-row format), row by row: per-variant correct/pass then → now,
    and every row whose label or pass/fail changed."""
    o, n = {r["idx"]: r for r in old}, {r["idx"]: r for r in new}
    names = next((list(r["runs"]) for r in new if r["runs"]), [])

    def tally(rows, v):
        runs = [(r, r["runs"][v]) for r in rows.values() if r["runs"] and v in r["runs"]]
        graded = [x for _, x in runs if x.get("quality") is not None]
        return {"correct": sum(x["label"] == r["expected"] for r, x in runs), "rows": len(runs),
                "passed": sum(x["quality"] >= PASS for x in graded), "graded": len(graded),
                "cost": sum(x["cost_usd"] or 0 for _, x in runs)}
    changed = []
    for i, r in sorted(n.items()):
        was = o.get(i)
        if not (was and was["runs"] and r["runs"]):
            continue
        for v, run in r["runs"].items():
            before = was["runs"].get(v)
            if not before:
                continue
            q0, q1 = before.get("quality"), run.get("quality")
            if before["label"] != run["label"] or (q0 is not None and q1 is not None and (q0 >= PASS) != (q1 >= PASS)):
                changed.append({"idx": i, "variant": v, "text": r["text"], "expected": r["expected"],
                                "before": before["label"], "after": run["label"], "q_before": q0, "q_after": q1})
    return {"variants": [{"key": v, "title": title(v), "before": tally(o, v), "after": tally(n, v)} for v in names],
            "changed": changed}


def _jev_text(questions: dict) -> str:
    """A Jev request's questions as readable text: name (type): instructions, then the criteria or options."""
    out = []
    for name, q in questions.items():
        out.append(f"{name} ({q.get('type', '?')}): {q.get('instructions', '')}")
        crit = q.get("criteria")
        if isinstance(crit, dict):
            out += [f"- {k}: {v}" for k, v in crit.items()]
        elif isinstance(crit, list):
            out += [f"- {v}" for v in crit]
        out += [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in q.items() if k not in ("type", "instructions", "criteria")]
        out.append("")
    return "\n".join(out).strip()


def prompt_rows(prompts: dict) -> list[dict]:
    """scripts/capture_prompts.py output → one row per distinct prompt, in first-seen order. Identical calls merge
    (21 asks the same Jev question once per item) and keep a count; the user message is the first call's."""
    rows: dict[tuple, dict] = {}
    for call in prompts.get("calls", []):
        if call["kind"] == "jev":
            kind, text = "Jev question", _jev_text(call["questions"])
            user = json.dumps(call.get("state"), ensure_ascii=False, indent=1)
        else:
            parts = ["\n\n".join(call["system"])] if call["system"] else []
            if call["tools"]:
                parts.append("Tools:\n" + "\n".join(f"- {t['name']}: {t['description']}" for t in call["tools"]))
            rf = call.get("response_format")
            if rf:
                parts.append("Structured output (JSON schema):\n" + json.dumps(rf.get("json_schema", rf), ensure_ascii=False))
            kind = "LLM + tools" if call["tools"] else "LLM system prompt"
            text, user = "\n\n".join(parts) or "(no system prompt)", "\n\n".join(call["user"])
        key = (kind, call.get("model"), text)
        if key in rows:
            rows[key]["count"] += 1
        else:
            rows[key] = {"n": len(rows) + 1, "kind": kind, "model": call.get("model"), "prompt": text, "user": user, "count": 1}
    return list(rows.values())
