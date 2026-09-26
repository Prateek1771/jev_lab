"""Drive the Streamlit page offline with a fake Result. No API keys, no spend."""

import importlib

from streamlit.testing.v1 import AppTest

from core.run import Result, Run


def test_page_renders_both_sections_and_metrics(monkeypatch):
    m = importlib.import_module("projects.01_classification.experiment")
    fake = Result.of(
        Run("jev", "fake-jev", "billing", 0.93, 100.0, 50, 0, 0.0000021),
        Run("baseline", "fake-llm", None, None, 400.0, 60, 3, 0.00004),
        Run("structured", "fake-llm", "billing", None, 450.0, 70, 6, 0.00005),
    )
    monkeypatch.setattr(m, "run_experiment", lambda text: fake)

    at = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception

    subheaders = [s.value for s in at.subheader]
    assert {"Jev-enhanced", "Baseline: plain prompt", "Baseline: structured output", "Experiment metrics"} <= set(subheaders)
    assert any("outside the schema" in e.value for e in at.error)   # baseline returned None


def test_dataset_run_survives_a_failing_row(monkeypatch):
    m = importlib.import_module("projects.02_detection.experiment")
    calls = {"n": 0}

    def fake_run(text):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("429 Too Many Requests")   # one bad row mid-batch
        return Result.of(
            Run("jev", "fake-jev", "urgent", None, 100.0, 50, 0, 0.000004, probability=0.9),
            Run("baseline", "fake-llm", "urgent", None, 900.0, 60, 1, 0.00002),
            Run("structured", "fake-llm", "urgent", None, 950.0, 70, 6, 0.00003),
        )

    monkeypatch.setattr(m, "run_experiment", fake_run)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.sidebar.radio[0].set_value("02 · Urgency Detection").run()
    next(b for b in at.button if b.label == "Run dataset").click().run()
    assert not at.exception
    assert calls["n"] == len(m.DATASET)                       # the batch kept going after the failure
    assert any("1 row(s) failed" in w.value for w in at.warning)
    assert any(s.value.startswith("Dataset run") for s in at.subheader)
    label_table = at.table[1].value                           # label counts, incl. an (invalid) row
    assert "(invalid)" in label_table.index
    assert label_table["Jev-enhanced"].sum() == len(m.DATASET) - 1   # every completed row counted exactly once
    assert any(s.value.startswith("Threshold sweep") for s in at.subheader)   # 02 declares SWEEP


def test_structured_input_is_json_and_bad_json_calls_nothing(monkeypatch):
    m = importlib.import_module("projects.04_routing.experiment")
    calls = []

    def fake_run(inp):
        calls.append(inp)
        jev = Run("jev", "fake-jev", "refund_auto", 0.93, 100.0, 200, 30, 0.000009,
                  raw={"band": "auto", "reason": "every automatic-refund condition holds",
                       "actions": ["start_refund_flow:auto", "route:queue.billing"]})
        return Result.of(jev, Run("baseline", "m", "refund_confirm", None, 900.0, 90, 2, 0.00002),
                         Run("structured", "m", "refund_auto", None, 950.0, 95, 6, 0.00003))

    monkeypatch.setattr(m, "run_experiment", fake_run)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.sidebar.radio[0].set_value("04 · Action Routing").run()
    assert at.text_area[0].label == "Input (JSON)"

    at.text_area[0].set_value('{"message": "half-edited').run()
    next(b for b in at.button if b.label == "Run experiment").click().run()
    assert any("not valid JSON" in e.value for e in at.error) and calls == []   # nothing sent

    at.text_area[0].set_value('{"message": "Charged twice", "order": "A-1", "prior_refunds_30d": 0}').run()
    next(b for b in at.button if b.label == "Run experiment").click().run()
    assert not at.exception and calls[-1]["order"] == "A-1"                      # parsed dict reached the backend
    assert any("start_refund_flow:auto" in c.value for c in at.code)            # the Jev column shows its actions


def test_citation_page_shows_each_claim_and_renamed_safety_rows(monkeypatch):
    m = importlib.import_module("projects.10_citation_verifier.experiment")
    claims = [{"text": "You have 30 days.", "cites": ["a"], "code": None, "verdict": "supported",
               "checks": [{"source": "a", "choice": "supports", "confidence": 0.95}]},
              {"text": "It is free.", "cites": ["zzz"], "code": "unknown_source", "verdict": "insufficient", "checks": []}]
    fake = Result.of(Run("jev", "fake-jev", "insufficient", 0.95, 90.0, 150, 0, 0.000006, raw={"claims": claims}),
                     Run("llm_judge", "fake-llm", "supported", None, 700.0, 300, 20, 0.00002),
                     Run("trust_citations", "(no model)", "supported", None, 0.0, 0, 0, 0.0))
    monkeypatch.setattr(m, "run_experiment", lambda inp: fake)
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value(m.TITLE).run()
    at.button[0].click().run()
    assert not at.exception
    code = " ".join(c.value for c in at.code)
    assert "[a] supports 0.95" in code and "unknown_source" in code
    at.button[1].click().run()   # dataset tab, every row the same fake
    assert not at.exception
    rows = " ".join(str(t.value.index.tolist()) for t in at.table)
    assert "Contradictions passed as SUPPORTED" in rows and "Unsafe calls ALLOWED" not in rows


def test_pii_page_shows_what_the_llm_receives(monkeypatch):
    m = importlib.import_module("projects.12_pii_detector.experiment")
    fake = Result.of(Run("jev", "fake-jev", "pii", None, 90.0, 90, 0, 0.000004, probability=0.9,
                         raw={"found": ["email: a@b.co"], "redacted": "mail me at [EMAIL]"}),
                     Run("regex", "(no model)", "pii", None, 0.0, 0, 0, 0.0),
                     Run("structured", "fake-llm", "pii", None, 700.0, 300, 5, 0.00002))
    monkeypatch.setattr(m, "run_experiment", lambda text: fake)
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value(m.TITLE).run()
    at.button[0].click().run()
    assert not at.exception and "mail me at [EMAIL]" in [c.value for c in at.code]


def test_escalation_page_says_human_not_invalid(monkeypatch):
    m = importlib.import_module("projects.17_agent_escalation.experiment")
    fake = Result.of(Run("jev", "fake-jev", None, 0.44, 90.0, 250, 0, 0.00001, raw={"route": "human", "reason": "human"}),
                     Run("llm_self_confidence", "fake-llm", "execute", 1.0, 700.0, 300, 9, 0.00002),
                     Run("always_review", "fake-frontier", "reject", None, 2700.0, 300, 9, 0.001))
    monkeypatch.setattr(m, "run_experiment", lambda inp: fake)
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value(m.TITLE).run()
    at.button[0].click().run()
    assert not at.exception
    assert any("Sent to a human" in i.value for i in at.info) and not any("outside the schema" in e.value for e in at.error)


def test_the_harness_result_renders(monkeypatch):
    """Found by Puppeteer on 24: its runs had `steps` but no `stop`, and the steps block raised KeyError.
    The runs here are built by 24's own _run, so the test renders the real raw shape."""
    m = importlib.import_module("projects.24_agent_harness.experiment")
    monkeypatch.setattr(m, "grade", lambda task, rubric, answer: {"quality": 0.9, "cost_usd": 0.00001})
    call = {"model": "m", "latency_ms": 10.0, "input_tokens": 100, "output_tokens": 5, "cost_usd": 0.00001}
    inp = m.EXAMPLES["Big output"]
    p = {"steps": [{"tool": "list_issues", "args": {}, "result": [{"id": "#412"}], "executed": True, "gate": "allow",
                    "filtered": "kept 1 of 31 items"}], "calls": [call], "stop": "finish"}
    runs = [m._run(v, p, "answered", "#412 and #418.", [call], call, inp, tier="fast", reason="r") for v in m.VARIANTS]
    monkeypatch.setattr(m, "run_experiment", lambda i: Result.of(*runs))
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.sidebar.radio[0].set_value(m.TITLE).run()
    next(b for b in at.button if b.label == "Run experiment").click().run()
    assert not at.exception
    assert any("stop: finish" in c.value and "list_issues({}) [allow] [kept 1 of 31 items]" in c.value for c in at.code)


def test_an_upstream_failure_is_an_error_message_not_a_crash(monkeypatch):
    """Found in the re-test: an OpenRouter 520 on one click showed a raw traceback on the page."""
    m = importlib.import_module("projects.01_classification.experiment")

    def boom(text):
        raise RuntimeError("Server error '520 <none>' for url 'https://openrouter.ai/api/alpha/decisions'")
    monkeypatch.setattr(m, "run_experiment", boom)
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception
    assert any("The run failed (RuntimeError)" in e.value and "run it again" in e.value for e in at.error)


def test_dollar_amounts_in_answers_are_not_rendered_as_math(monkeypatch):
    """Found in the re-test: '$120.00 plus $7.50' in 24's frontier answer rendered as garbled LaTeX."""
    from core.ui import md_text
    assert md_text("$120.00 plus $7.50 = $127.50") == r"\$120.00 plus \$7.50 = \$127.50"
    m = importlib.import_module("projects.05_model_router.experiment")
    runs = [Run(v, "m", "fast", None, 10.0, 1, 1, 0.0, quality=0.9, raw={"answer": "Total: $120.00 plus $7.50.", "reason": "r"})
            for v in ("jev", "llm_router", "frontier")]
    monkeypatch.setattr(m, "run_experiment", lambda inp: Result.of(*runs))
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.sidebar.radio[0].set_value(m.TITLE).run()
    next(b for b in at.button if b.label == "Run experiment").click().run()
    assert not at.exception
    assert any(r"\$120.00 plus \$7.50" in md.value for md in at.markdown)


def test_query_param_picks_the_project_and_links_back_to_the_new_ui():
    """The web UI's "Streamlit" toggle opens ?p=NN; the sidebar's link opens the same project in the web UI."""
    from config import settings
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.query_params["p"] = "13"
    at.run()
    assert not at.exception
    assert at.sidebar.radio[0].value.startswith("13 ") and at.header[0].value.startswith("13 ")
    link = at.sidebar.get("link_button")[0]
    assert link.proto.url == f"{settings.WEB_UI_URL}/p/13"
    at.sidebar.radio[0].set_value(next(o for o in at.sidebar.radio[0].options if o.startswith("02 "))).run()
    assert at.query_params["p"] == ["02"] and at.sidebar.get("link_button")[0].proto.url.endswith("/p/02")


def test_an_unknown_project_id_falls_back_to_the_first():
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.query_params["p"] = "99"
    at.run()
    assert not at.exception and at.sidebar.radio[0].value.startswith("01 ")
