"""Day 11: a mock agent that times out (or partially completes), and
explicit timeout handling in the runner CLI."""

from harness.cli import evaluate_scenario, print_report, ScenarioOutcome
from harness.evaluators import ToolCallSequenceEvaluator
from harness.mock_agent import AgentResult, AgentTimeoutError, TimesOutAgent
from harness.schema import ScenarioSpec

CORRECT_SCRIPT = {
    "Create a ticket in the DEMO project titled 'Fix login bug'": AgentResult(
        tool_calls=["list_projects", "create_ticket"],
        output="Created DEMO-42.",
    ),
}

TICKET_SCENARIO = ScenarioSpec(
    id="create_ticket",
    role="ticket_agent",
    input="Create a ticket in the DEMO project titled 'Fix login bug'",
    expected_tool_calls=["list_projects", "create_ticket"],
)


# --- TimesOutAgent: total timeout -----------------------------------------

def test_full_timeout_raises_instead_of_returning():
    agent = TimesOutAgent(CORRECT_SCRIPT)

    try:
        agent.run(TICKET_SCENARIO.input)
        assert False, "expected AgentTimeoutError"
    except AgentTimeoutError as e:
        assert TICKET_SCENARIO.input in str(e)


# --- TimesOutAgent: partial completion ------------------------------------

def test_partial_completion_returns_truncated_tool_calls():
    agent = TimesOutAgent(CORRECT_SCRIPT, partial_after=1)

    result = agent.run(TICKET_SCENARIO.input)

    assert result.tool_calls == ["list_projects"]
    assert result.output == ""
    assert result.handoff_context is None


def test_partial_completion_with_zero_calls_returns_empty_list():
    agent = TimesOutAgent(CORRECT_SCRIPT, partial_after=0)

    result = agent.run(TICKET_SCENARIO.input)

    assert result.tool_calls == []


def test_partial_completion_is_just_a_normal_evaluator_failure():
    # No special-casing needed: a truncated tool-call list is exactly the
    # kind of thing ToolCallSequenceEvaluator already knows how to fail.
    agent = TimesOutAgent(CORRECT_SCRIPT, partial_after=1)
    evaluator = ToolCallSequenceEvaluator(mode="exact")

    result = agent.run(TICKET_SCENARIO.input)
    outcome = evaluator.evaluate(TICKET_SCENARIO, result)

    assert outcome.passed is False


# --- evaluate_scenario: timeout handling -----------------------------------

def test_evaluate_scenario_reports_timeout_distinctly_from_crash():
    outcome = evaluate_scenario(TICKET_SCENARIO, agent=TimesOutAgent(CORRECT_SCRIPT))

    assert outcome.passed is False
    assert outcome.timed_out is True
    assert outcome.crashed is False
    assert TICKET_SCENARIO.input in outcome.failures[0]


def test_evaluate_scenario_still_uses_the_registry_when_no_agent_is_given():
    # No explicit agent passed — falls back to the real registered
    # ticket_agent, which is scripted correctly, so this should pass.
    outcome = evaluate_scenario(TICKET_SCENARIO)

    assert outcome.passed is True


def test_one_timed_out_scenario_does_not_stop_others():
    good_outcome = evaluate_scenario(TICKET_SCENARIO)
    timeout_outcome = evaluate_scenario(TICKET_SCENARIO, agent=TimesOutAgent(CORRECT_SCRIPT))

    assert good_outcome.passed is True
    assert timeout_outcome.timed_out is True


# --- print_report -----------------------------------------------------------

def test_print_report_shows_timeout_status(capsys):
    outcomes = [
        ScenarioOutcome("good", passed=True),
        ScenarioOutcome("slow", passed=False, failures=("timed out",), timed_out=True),
    ]
    print_report(outcomes)

    output = capsys.readouterr().out
    assert "[PASS] good" in output
    assert "[TIMEOUT] slow" in output
    assert "[FAIL] slow" not in output  # timeout status takes precedence over generic FAIL
