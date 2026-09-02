"""Day 5: rule-based output-format evaluator (regex + JSON schema)."""

from harness.evaluators import OutputFormatEvaluator
from harness.mock_agent import AgentResult
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario
from harness.schema import ScenarioSpec

NO_FORMAT_CHECK = ScenarioSpec(id="x", role="agent_a", input="hello")


def test_scenario_with_no_format_checks_trivially_passes():
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output="literally anything")

    assert evaluator.evaluate(NO_FORMAT_CHECK, result).passed is True


# --- regex pattern -----------------------------------------------------

def test_real_scenario_output_pattern_passes_on_matching_output():
    scenario = load_scenario(SCENARIOS_DIR / "create_ticket.yaml")
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output="Created DEMO-42.")

    outcome = evaluator.evaluate(scenario, result)

    assert outcome.passed is True


def test_real_scenario_output_pattern_fails_on_missing_ticket_key():
    scenario = load_scenario(SCENARIOS_DIR / "create_ticket.yaml")
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output="Ticket created.")  # no DEMO-<number>

    outcome = evaluator.evaluate(scenario, result)

    assert outcome.passed is False
    assert "DEMO" in outcome.reasoning


# --- JSON schema ---------------------------------------------------------

SCHEMA_SCENARIO = ScenarioSpec(
    id="json-output",
    role="project_agent",
    input="irrelevant for this test",
    expected_output_schema={"project_key": "str", "issue_count": "int"},
)


def test_schema_check_passes_on_matching_json():
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output='{"project_key": "DEMO", "issue_count": 3}')

    assert evaluator.evaluate(SCHEMA_SCENARIO, result).passed is True


def test_schema_check_fails_on_invalid_json():
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output="not json at all")

    outcome = evaluator.evaluate(SCHEMA_SCENARIO, result)

    assert outcome.passed is False
    assert "not valid JSON" in outcome.reasoning


def test_schema_check_fails_on_non_object_json():
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output="[1, 2, 3]")

    outcome = evaluator.evaluate(SCHEMA_SCENARIO, result)

    assert outcome.passed is False
    assert "JSON object" in outcome.reasoning


def test_schema_check_fails_on_missing_key():
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output='{"project_key": "DEMO"}')  # missing issue_count

    outcome = evaluator.evaluate(SCHEMA_SCENARIO, result)

    assert outcome.passed is False
    assert "issue_count" in outcome.reasoning


def test_schema_check_fails_on_wrong_type():
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output='{"project_key": "DEMO", "issue_count": "three"}')

    outcome = evaluator.evaluate(SCHEMA_SCENARIO, result)

    assert outcome.passed is False
    assert "issue_count" in outcome.reasoning


def test_bool_is_not_mistakenly_accepted_as_int():
    # In Python, bool is a subclass of int — isinstance(True, int) is True.
    # A schema check for "int" should still reject a bool, since a real
    # count field getting `true`/`false` instead of a number is a bug the
    # evaluator should catch, not silently pass.
    schema_scenario = ScenarioSpec(
        id="strict-int",
        role="agent_a",
        input="x",
        expected_output_schema={"issue_count": "int"},
    )
    evaluator = OutputFormatEvaluator()
    result = AgentResult(output='{"issue_count": true}')

    assert evaluator.evaluate(schema_scenario, result).passed is False
