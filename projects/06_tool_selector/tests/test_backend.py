"""Project 06, offline: the stop rules, the calculator's safety, and whole agent loops with scripted pickers."""

import importlib

import pytest
from langchain_core.messages import AIMessage

exp = importlib.import_module("projects.06_tool_selector.experiment")
jev_client = importlib.import_module("projects.06_tool_selector.jev_client")
llm = importlib.import_module("projects.06_tool_selector.llm")
policy = importlib.import_module("projects.06_tool_selector.policy")
tools = importlib.import_module("projects.06_tool_selector.tools")


@pytest.mark.parametrize("choice,conf,expected", [
    ("database", 0.90, "database"),
    ("database", 0.30, "ask_user"),    # unsure: ask, don't guess a tool
    ("finish", 0.30, "ask_user"),      # unsure applies to stopping too
    ("finish", 0.90, "finish"),
    ("database", None, "database"),    # LLM selectors have no confidence, so they can't be gated
])
def test_next_step(choice, conf, expected):
    assert policy.next_step(choice, conf)[0] == expected


@pytest.mark.parametrize("called,stop,label", [
    ([], "finish", "none"), (["database", "calculator"], "finish", "database > calculator"),
    ([], "ask_user", "ask_user"), (["database"], "ask_user", "database > ask_user"),
    (["database"] * 4, None, None),    # never stopped: unfinished, counted as invalid
])
def test_trajectory(called, stop, label):
    assert policy.trajectory(called, stop) == label


@pytest.mark.parametrize("expr,out", [("(120 + 7.5) * 1.2", "153"), ("318.40 / 7", "45.48571429"),
                                      ("2 ** 31 - 1", "2147483647"), ("-3 % 2", "1")])
def test_calculator(expr, out):
    assert tools.calculator(expr) == out


def test_caret_means_power():
    """Real test: tool_calling wrote `2^31 - 1` and got 'not allowed: BinOp' (Python's ^ is XOR)."""
    assert tools.calculator("2^31 - 1") == "2147483647"


def test_side_effect_tools_say_the_job_is_done():
    """Real test: "RECORDED, not sent" made Jev send the same email up to 4 times."""
    assert tools.send_email("a@b.test", "s", "b").startswith("Sent") and tools.create_ticket("t", "low").startswith("Created")


def test_search_answers_or_says_nothing_found():
    """Real test: a canned "summarizing the answer" with no answer made the native agent search 4 times."""
    assert "14 million" in tools.search_web("population of Tokyo") and tools.search_web("xyz").startswith("No results")
    assert "Clarke" in tools.search_web("latest Nobel Prize in Physics winner")   # a canned hit must contain the answer


@pytest.mark.parametrize("expr", ["__import__('os').system('x')", "open('f')", "a.b", "2 ** 100000", "1 / 0", "1 +"])
def test_calculator_rejects_anything_but_arithmetic(expr):
    assert tools.calculator(expr).startswith("error")


def call(cost=0.00001):
    return {"latency_ms": 100.0, "input_tokens": 50, "output_tokens": 5, "cost_usd": cost}


@pytest.fixture
def scripted(monkeypatch):
    """Scripted pickers and arg writer. Records what each picker saw and which tools got arguments."""
    rec = {"jev_seen": [], "args_for": []}

    def script(picks):
        jev_picks, llm_picks, native = (iter(p) for p in picks)

        def jev_pick(request, observations):
            rec["jev_seen"].append(observations)
            choice, conf = next(jev_picks)
            return {"choice": choice, "confidence": conf, "model": "typesafe/jev-1.13-20260917"} | call(0.000004)

        def write_args(tool, request, observations):
            rec["args_for"].append(tool)
            return ({"order_id": "A-104"} if tool == "database" else {"expression": "(120 + 7.5) * 1.2"}), call()

        monkeypatch.setattr(jev_client, "pick_tool", jev_pick)
        monkeypatch.setattr(llm, "write_args", write_args)
        monkeypatch.setattr(llm, "pick_tool", lambda request, observations: (next(llm_picks), call()))
        monkeypatch.setattr(llm, "native_step", lambda messages: (next(native), call()))
        return rec
    return script


def tool_msg(name, args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


TWO_TOOLS = ([("database", 0.9), ("calculator", 0.8), ("finish", 0.95)],
             ["database", "calculator", "finish"],
             [tool_msg("database", {"order_id": "A-104"}), tool_msg("calculator", {"expression": "127.5 * 1.2"}),
              AIMessage("It comes to 153.")])


def test_two_step_loop_offline(scripted):
    rec = scripted(TWO_TOOLS)
    r = exp.run_experiment(exp.EXAMPLES["Two tools"])
    assert [run.label for run in r.runs.values()] == ["database > calculator"] * 3
    jev = r.runs["jev"]
    assert jev.confidence == 0.8                                  # the weakest pick
    assert jev.cost_usd == pytest.approx(3 * 0.000004 + 2 * 0.00001)   # 3 picks + 2 arg writes
    assert jev.model == "typesafe/jev-1.13-20260917"
    assert "'subtotal': 120.0" in rec["jev_seen"][1][0]["result"]     # step 2 saw step 1's result
    assert jev.raw["steps"][1]["result"] == "153"
    assert r.trace_url is None and r.trace_id is None             # tracing is off in tests (conftest)


def test_arguments_are_written_only_for_chosen_tools(scripted):
    rec = scripted(TWO_TOOLS)
    exp.run_experiment(exp.EXAMPLES["Two tools"])
    assert sorted(rec["args_for"]) == ["calculator", "calculator", "database", "database"]   # jev + llm_selector, never a stop


def test_unsure_jev_asks_instead_of_calling(scripted):
    rec = scripted(([("send_email", 0.30)], ["ask_user"], [tool_msg("ask_user", {"question": "Send what, to whom?"})]))
    r = exp.run_experiment(exp.EXAMPLES["Unclear"])
    assert [run.label for run in r.runs.values()] == ["ask_user"] * 3
    assert rec["args_for"] == [] and "unsure" in r.runs["jev"].raw["reason"]


def test_an_agent_that_never_stops_is_unfinished(scripted):
    forever = [("database", 0.9)] * 10
    scripted((forever, ["database"] * 10, [tool_msg("database", {"order_id": "C-9"})] * 10))
    r = exp.run_experiment(exp.EXAMPLES["One tool"])
    for run in r.runs.values():
        assert run.label is None and len(run.raw["steps"]) == policy.MAX_STEPS
        assert run.raw["stop"].startswith("gave up")


def test_missing_cost_makes_the_run_cost_unknown(scripted, monkeypatch):
    scripted(([("finish", 0.9)], ["finish"], [AIMessage("You're welcome!")]))
    monkeypatch.setattr(llm, "pick_tool", lambda request, observations: ("finish", call(None)))
    r = exp.run_experiment(exp.EXAMPLES["No tool"])
    assert r.runs["llm_selector"].cost_usd is None and r.runs["jev"].cost_usd is not None


class FakeLLM:
    def __init__(self, out):
        self.out, self.config = out, None

    def with_structured_output(self, *args, **kwargs):
        return self

    def invoke(self, messages, config=None):
        self.config = config
        return self.out


def test_llm_selector_outside_the_enum_asks(monkeypatch):
    monkeypatch.setattr(llm, "_llm", lambda: FakeLLM(None))
    monkeypatch.setattr(llm, "metered_call", lambda name, runnable, messages: ({"parsed": {"next": "delete_db"}}, call()))
    assert llm.pick_tool("r", [])[0] == "ask_user"
