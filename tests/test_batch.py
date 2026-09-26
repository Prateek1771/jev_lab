"""The batch numbers: what counts as correct, what's excluded, and what's never faked."""

import pytest

from core.run import Result, Run
from core.ui import cheapest, safety, summarize, sweep


def run(variant, label, ms, cost=0.00001):
    return Run(variant, "m", label, None, ms, 10, 1, cost)


def row(expected, jev_label, base_label, jev_ms=100.0, base_ms=1000.0, base_cost=0.00002):
    return {"text": "t", "expected": expected, "error": None,
            "result": Result.of(run("jev", jev_label, jev_ms), run("baseline", base_label, base_ms, base_cost))}


ROWS = [
    row("urgent", "urgent", "urgent", 100, 1000),
    row("urgent", "not_urgent", None, 200, 2000, base_cost=None),   # jev wrong; baseline invalid, no cost
    row("not_urgent", "not_urgent", "urgent", 300, 3000),
    row("not_urgent", "not_urgent", "not_urgent", 400, 4000),
    {"text": "t", "expected": "urgent", "result": None, "error": "HTTPStatusError: 429"},
]


def test_accuracy_counts_invalid_as_wrong_and_excludes_errors():
    j, b = summarize(ROWS, "jev"), summarize(ROWS, "baseline")
    assert (j["rows"], j["errors"]) == (5, 1)
    assert j["accuracy"] == pytest.approx(3 / 4)
    assert b["accuracy"] == pytest.approx(2 / 4) and b["invalid"] == 1


def test_latency_percentiles():
    j = summarize(ROWS, "jev")
    assert j["p50_ms"] == pytest.approx(250)       # median of 100, 200, 300, 400
    assert 385 <= j["p95_ms"] <= 400


def test_missing_cost_is_counted_not_zeroed():
    b = summarize(ROWS, "baseline")
    assert b["cost_missing"] == 1
    assert b["total_cost"] == pytest.approx(0.00006)   # the three rows that reported cost


def test_label_counts_expose_never_chosen_labels():
    assert summarize(ROWS, "jev")["labels"] == {"urgent": 1, "not_urgent": 3}
    assert summarize(ROWS, "baseline")["labels"]["(invalid)"] == 1


def test_all_rows_failed():
    s = summarize([{"text": "t", "expected": "x", "result": None, "error": "boom"}], "jev")
    assert s["accuracy"] is None and s["p50_ms"] is None


# --- threshold sweep: pure, over stored values ---

def prow(expected, p):
    return {"text": "t", "expected": expected, "error": None,
            "result": Result.of(Run("jev", "m", None, None, 1.0, 1, 0, 0.0, probability=p))}


SWEEP_ROWS = [prow("urgent", 0.9), prow("urgent", 0.6), prow("urgent", 0.3),        # one urgent row Jev is unsure about
              prow("not_urgent", 0.55), prow("not_urgent", 0.2), prow("not_urgent", 0.05),
              {"text": "t", "expected": "urgent", "result": None, "error": "boom"}]   # failed rows are skipped


def test_sweep_counts_per_threshold():
    by_t = {p["threshold"]: p for p in sweep(SWEEP_ROWS, "urgent", "probability", [0.0, 0.5, 0.7, 1.0])}
    assert (by_t[0.0]["tp"], by_t[0.0]["fp"], by_t[0.0]["fn"]) == (3, 3, 0)   # flag everything
    assert (by_t[0.5]["tp"], by_t[0.5]["fp"], by_t[0.5]["fn"]) == (2, 1, 1)
    assert (by_t[0.7]["tp"], by_t[0.7]["fp"], by_t[0.7]["fn"]) == (1, 0, 2)
    assert (by_t[1.0]["tp"], by_t[1.0]["fn"]) == (0, 3)                      # flag nothing
    assert by_t[0.5]["tp"] + by_t[0.5]["fp"] + by_t[0.5]["fn"] + by_t[0.5]["tn"] == 6


def test_cheapest_follows_the_cost_of_each_mistake():
    grid = [i / 20 for i in range(21)]
    # misses are expensive -> threshold drops low enough to catch the 0.3 row
    assert cheapest(sweep(SWEEP_ROWS, "urgent", "probability", grid), cost_fn=10, cost_fp=1)["fn"] == 0
    # false alarms are expensive -> threshold rises above the 0.55 false alarm
    assert cheapest(sweep(SWEEP_ROWS, "urgent", "probability", grid), cost_fn=1, cost_fp=10)["fp"] == 0


def test_sweep_on_score_values():
    rows = [{"text": "t", "expected": e, "error": None,
             "result": Result.of(Run("jev", "m", None, None, 1.0, 1, 0, 0.0, score=s))}
            for e, s in [("high", 1.9), ("high", 1.2), ("medium", 1.0), ("low", 0.1)]]
    by_t = {p["threshold"]: p for p in sweep(rows, "high", "score", [1.1, 1.5])}
    assert (by_t[1.1]["tp"], by_t[1.1]["fn"]) == (2, 0) and (by_t[1.5]["tp"], by_t[1.5]["fn"]) == (1, 1)


# --- graded answers (05+): quality per dollar ---

def qrow(quality, cost):
    return {"text": "t", "expected": "fast", "error": None,
            "result": Result.of(Run("jev", "m", "fast", None, 1.0, 1, 0, cost, quality=quality))}


def test_pass_rate_and_cost_per_passing_answer():
    s = summarize([qrow(0.9, 0.01), qrow(0.5, 0.01), qrow(0.2, 0.02)], "jev")   # 0.5 passes: the cut is >=
    assert (s["graded"], s["passed"]) == (3, 2)
    assert s["pass_rate"] == pytest.approx(2 / 3)
    assert s["cost_per_pass"] == pytest.approx(0.04 / 2)   # failed answers still cost money


def test_no_passing_answers_gives_none_not_a_division_error():
    s = summarize([qrow(0.1, 0.01)], "jev")
    assert s["pass_rate"] == 0 and s["cost_per_pass"] is None


def test_ungraded_projects_report_no_pass_rate():
    assert summarize(ROWS, "jev")["pass_rate"] is None


# --- gates (07+): what got through ---

def grow(expected, label):
    return {"text": "t", "expected": expected, "error": None,
            "result": Result.of(Run("jev", "m", label, None, 1.0, 1, 0, 0.0))}


def test_safety_counts_what_got_through():
    rows = [grow("block", "block"), grow("block", "confirm"), grow("block", "allow"),   # one unsafe call ALLOWED
            grow("allow", "allow"), grow("allow", "confirm"), grow("confirm", "block")]
    g = safety(rows, "jev", "block", "allow")
    assert (g["unsafe_blocked"], g["unsafe_allowed"], g["unsafe"]) == (1, 1, 3)
    assert g["block_rate"] == pytest.approx(1 / 3)
    assert (g["safe_stopped"], g["safe"]) == (1, 2) and g["false_positive_rate"] == pytest.approx(0.5)


def test_safety_with_no_unsafe_rows_is_none():
    g = safety([grow("allow", "allow")], "jev", "block", "allow")
    assert g["block_rate"] is None and g["false_positive_rate"] == 0


# --- retrieval filters (08+): precision and recall, averaged only where defined ---

def rrow(precision, recall):
    return {"text": "t", "expected": "answer", "error": None,
            "result": Result.of(Run("jev", "m", "answer", None, 1.0, 1, 0, 0.0,
                                    raw={"precision": precision, "recall": recall}))}


def test_precision_recall_average_skips_undefined_rows():
    s = summarize([rrow(1.0, 1.0), rrow(0.5, None), rrow(None, None)], "jev")
    assert s["precision"] == pytest.approx(0.75) and s["recall"] == pytest.approx(1.0)
    assert summarize(ROWS, "jev")["precision"] is None   # projects without retrieval report nothing


def test_raw_metrics_cover_ranking_too():
    rows = [{"text": "t", "expected": "answer", "error": None,
             "result": Result.of(Run("jev", "m", "answer", None, 1.0, 1, 0, 0.0, raw={"ndcg": n, "mrr": m}))}
            for n, m in [(1.0, 1.0), (0.5, 0.5), (None, None)]]
    s = summarize(rows, "jev")
    assert s["ndcg"] == pytest.approx(0.75) and s["mrr"] == pytest.approx(0.75) and s["precision"] is None


def test_a_run_handed_to_a_human_is_not_invalid():
    """Found clicking through 17: routing to a human (label None, route human) showed 'Answer outside the schema'
    and counted as an invalid answer."""
    from core.ui import handed_off, outcome
    human = Run("jev", "m", None, 0.4, 1.0, 1, 0, 0.0, raw={"route": "human"})
    broken = Run("jev", "m", None, None, 1.0, 1, 0, 0.0)
    assert handed_off(human) and not handed_off(broken)
    assert (outcome(human), outcome(broken)) == ("(human)", "(invalid)")
    rows = [{"text": "t", "expected": "execute", "error": None, "result": Result.of(r)} for r in (human, broken)]
    s = summarize(rows, "jev")
    assert s["invalid"] == 1 and s["labels"]["(human)"] == 1 and s["labels"]["(invalid)"] == 1
