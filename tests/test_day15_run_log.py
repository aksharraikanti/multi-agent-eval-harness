"""Day 15: reproducibility pass — log a run to JSON, replay it later
against the evaluators, without touching the agent or any tool server
during replay.
"""

from harness.agent_registry import get_agent
from harness.evaluators import ContextLossEvaluator, OutputFormatEvaluator, ToolCallSequenceEvaluator
from harness.mock_agent import AgentResult
from harness.runner import SCENARIOS_DIR
from harness.run_log import load_run_log, record_run, replay, RunRecord, write_run_log
from harness.scenario_loader import load_scenario


def test_record_run_generates_a_run_id_when_none_given():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    result = AgentResult(tool_calls=["list_projects"], output="ok")

    record = record_run(scenario, result)

    assert isinstance(record, RunRecord)
    assert record.run_id  # non-empty


def test_record_run_preserves_an_explicit_run_id():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    result = AgentResult(tool_calls=["list_projects"], output="ok")

    record = record_run(scenario, result, run_id="fixed-id-123")

    assert record.run_id == "fixed-id-123"


def test_record_run_captures_scenario_and_result_as_plain_dicts():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    result = AgentResult(tool_calls=["list_projects"], output="ok")

    record = record_run(scenario, result)

    assert record.scenario["id"] == "list_projects"
    assert record.agent_result["tool_calls"] == ["list_projects"]
    assert record.agent_result["output"] == "ok"


# --- write/load round-trip -------------------------------------------------

def test_write_then_load_round_trips_exactly(tmp_path):
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    agent = get_agent(scenario.role)
    result = agent.run(scenario.input)

    original = record_run(scenario, result, run_id="round-trip-test")
    log_path = tmp_path / "runs" / "round-trip-test.json"
    write_run_log(original, log_path)

    loaded = load_run_log(log_path)

    assert loaded == original
    assert loaded.agent_result["handoff_context"] == {
        "project_key": "DEMO",
        "title": "Fix login bug",
        "reporter_email": "user@example.com",
    }


def test_write_run_log_creates_missing_parent_directories(tmp_path):
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    result = AgentResult(tool_calls=["list_projects"], output="ok")
    record = record_run(scenario, result)

    nested_path = tmp_path / "a" / "b" / "c" / "run.json"
    write_run_log(record, nested_path)

    assert nested_path.exists()


# --- replay -----------------------------------------------------------------

def test_replay_reproduces_the_same_outcome_as_evaluating_live():
    scenario = load_scenario(SCENARIOS_DIR / "create_ticket.yaml")
    agent = get_agent(scenario.role)
    result = agent.run(scenario.input)

    evaluators = [ToolCallSequenceEvaluator(mode="exact"), OutputFormatEvaluator()]
    live_outcomes = [e.evaluate(scenario, result) for e in evaluators]

    record = record_run(scenario, result)
    replayed_outcomes = replay(record, evaluators)

    assert [o.passed for o in replayed_outcomes] == [o.passed for o in live_outcomes]
    assert [o.reasoning for o in replayed_outcomes] == [o.reasoning for o in live_outcomes]


def test_replay_works_from_a_file_loaded_from_disk(tmp_path):
    # The realistic path: record today, write to disk, load in a later
    # process, replay without ever touching the original scenario/agent
    # objects again.
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    agent = get_agent(scenario.role)
    result = agent.run(scenario.input)

    write_run_log(record_run(scenario, result, run_id="disk-replay"), tmp_path / "disk-replay.json")

    loaded = load_run_log(tmp_path / "disk-replay.json")
    outcomes = replay(loaded, [ContextLossEvaluator(check_hallucinated_keys=True)])

    assert all(o.passed for o in outcomes)


def test_replay_detects_a_failure_that_was_captured_at_record_time():
    scenario = load_scenario(SCENARIOS_DIR / "create_ticket.yaml")
    # A deliberately wrong result, as if it had been captured from a
    # buggy agent run — replay should still faithfully report the
    # failure, not paper over it.
    broken_result = AgentResult(tool_calls=["create_ticket"], output="Created DEMO-42.")

    record = record_run(scenario, broken_result)
    outcomes = replay(record, [ToolCallSequenceEvaluator(mode="exact")])

    assert outcomes[0].passed is False


def test_replay_signature_has_no_way_to_touch_an_agent():
    # Structural guarantee, not a runtime check: replay()'s parameters
    # are (record, evaluators) — there is no agent or server argument it
    # could invoke even by mistake.
    import inspect

    params = list(inspect.signature(replay).parameters)

    assert params == ["record", "evaluators"]
