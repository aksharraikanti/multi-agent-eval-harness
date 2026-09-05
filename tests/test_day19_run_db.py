"""Day 19: SQLite run-log schema (runs, scenarios, evaluator_results)."""

from harness.cli import evaluate_scenario, run_suite, ScenarioOutcome
from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult, TimesOutAgent
from harness.run_db import connect, write_run
from harness.runner import SCENARIOS_DIR
from harness.schema import ScenarioSpec


def test_connect_creates_all_three_tables(tmp_path):
    conn = connect(tmp_path / "runs.db")

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }

    assert {"runs", "scenarios", "evaluator_results"} <= tables


def test_connect_is_safe_to_call_twice_against_the_same_file(tmp_path):
    path = tmp_path / "runs.db"
    connect(path)
    connect(path)  # must not raise


def test_write_run_inserts_one_runs_row_with_correct_totals(tmp_path):
    conn = connect(tmp_path / "runs.db")
    outcomes = [
        ScenarioOutcome("a", passed=True),
        ScenarioOutcome("b", passed=False, failures=("nope",)),
    ]

    run_id = write_run(conn, outcomes)

    row = conn.execute("SELECT run_id, total, passed FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert row == (run_id, 2, 1)


def test_write_run_uses_a_provided_run_id():
    conn = connect(":memory:")

    run_id = write_run(conn, [ScenarioOutcome("a", passed=True)], run_id="fixed-run-id")

    assert run_id == "fixed-run-id"
    assert conn.execute("SELECT run_id FROM runs").fetchone() == ("fixed-run-id",)


def test_write_run_inserts_one_scenarios_row_per_outcome():
    conn = connect(":memory:")
    outcomes = [
        ScenarioOutcome("a", passed=True),
        ScenarioOutcome("b", passed=False, crashed=True),
        ScenarioOutcome("c", passed=False, timed_out=True),
    ]

    run_id = write_run(conn, outcomes)

    rows = conn.execute(
        "SELECT scenario_id, passed, crashed, timed_out FROM scenarios WHERE run_id = ? ORDER BY scenario_id",
        (run_id,),
    ).fetchall()

    assert rows == [
        ("a", 1, 0, 0),
        ("b", 0, 1, 0),
        ("c", 0, 0, 1),
    ]


def test_write_run_inserts_evaluator_results_for_each_evaluator_that_ran():
    conn = connect(":memory:")
    outcome = ScenarioOutcome(
        "a",
        passed=False,
        failures=("wrong tool calls",),
        evaluator_results=(
            ("ToolCallSequenceEvaluator", EvaluationResult(passed=False, reasoning="wrong tool calls")),
            ("OutputFormatEvaluator", EvaluationResult(passed=True, reasoning="output format checks satisfied")),
        ),
    )

    write_run(conn, [outcome])

    rows = conn.execute(
        "SELECT evaluator_name, passed, reasoning FROM evaluator_results ORDER BY evaluator_name"
    ).fetchall()

    assert rows == [
        ("OutputFormatEvaluator", 1, "output format checks satisfied"),
        ("ToolCallSequenceEvaluator", 0, "wrong tool calls"),
    ]


def test_crashed_scenario_has_no_evaluator_results():
    conn = connect(":memory:")
    scenario = ScenarioSpec(id="ghost", role="nonexistent_agent", input="hello")
    outcome = evaluate_scenario(scenario)  # crashes: unregistered role

    write_run(conn, [outcome])

    count = conn.execute("SELECT COUNT(*) FROM evaluator_results").fetchone()[0]
    assert count == 0


def test_timed_out_scenario_has_no_evaluator_results():
    conn = connect(":memory:")
    scenario = ScenarioSpec(
        id="slow",
        role="ticket_agent",
        input="Create a ticket in the DEMO project titled 'Fix login bug'",
    )
    script = {scenario.input: AgentResult()}
    outcome = evaluate_scenario(scenario, agent=TimesOutAgent(script))

    write_run(conn, [outcome])

    count = conn.execute("SELECT COUNT(*) FROM evaluator_results").fetchone()[0]
    assert count == 0


def test_evaluator_results_reference_the_correct_scenario_row_when_multiple_scenarios_exist():
    conn = connect(":memory:")
    outcomes = [
        ScenarioOutcome(
            "a",
            passed=True,
            evaluator_results=(("EvalX", EvaluationResult(passed=True, reasoning="a passed")),),
        ),
        ScenarioOutcome(
            "b",
            passed=False,
            evaluator_results=(("EvalX", EvaluationResult(passed=False, reasoning="b failed")),),
        ),
    ]

    write_run(conn, outcomes)

    reasoning_by_scenario = conn.execute(
        """SELECT s.scenario_id, e.reasoning
           FROM evaluator_results e
           JOIN scenarios s ON s.id = e.scenario_row_id
           ORDER BY s.scenario_id"""
    ).fetchall()

    assert reasoning_by_scenario == [("a", "a passed"), ("b", "b failed")]


# --- integration: the real scenario suite, end to end ----------------------

def test_real_scenario_suite_writes_cleanly_and_matches_the_cli_summary(tmp_path):
    outcomes = run_suite([SCENARIOS_DIR])
    conn = connect(tmp_path / "runs.db")

    run_id = write_run(conn, outcomes)

    run_row = conn.execute("SELECT total, passed FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert run_row == (len(outcomes), sum(1 for o in outcomes if o.passed))

    # Every registered scenario passes today (see test_day6_cli.py) — so
    # every evaluator_results row for this run should also say passed=1.
    evaluator_pass_flags = conn.execute(
        """SELECT e.passed FROM evaluator_results e
           JOIN scenarios s ON s.id = e.scenario_row_id
           WHERE s.run_id = ?""",
        (run_id,),
    ).fetchall()
    assert evaluator_pass_flags  # at least one row exists
    assert all(row == (1,) for row in evaluator_pass_flags)
