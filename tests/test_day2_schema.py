"""Day 2: scenario spec schema + YAML loader."""

import pytest
from pydantic import ValidationError

from harness.schema import ScenarioSpec
from harness.scenario_loader import load_scenario, load_scenarios
from harness.runner import SCENARIOS_DIR


def test_loads_real_scenario_file_into_schema():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")

    assert isinstance(scenario, ScenarioSpec)
    assert scenario.id == "list_projects"
    assert scenario.role == "project_agent"
    assert scenario.expected_tool_calls == ["list_projects"]
    assert scenario.success_criteria is not None


def test_handoff_fields_are_optional():
    # A single-agent scenario (no handoff_to/context_passed at all) must
    # still validate — those fields are additive, not required, so day 1's
    # scenario never needs a migration when day 8 adds them.
    scenario = ScenarioSpec(id="x", role="agent_a", input="hello")

    assert scenario.handoff_to is None
    assert scenario.context_passed is None
    assert scenario.expected_tool_calls == []


def test_handoff_fields_can_be_set():
    scenario = ScenarioSpec(
        id="handoff-example",
        role="orchestrator",
        input="hello",
        handoff_to="worker_agent",
        context_passed={"user_id": 1, "ticket_id": "DEMO-1"},
    )

    assert scenario.handoff_to == "worker_agent"
    assert scenario.context_passed == {"user_id": 1, "ticket_id": "DEMO-1"}


def test_missing_required_field_raises():
    with pytest.raises(ValidationError):
        ScenarioSpec(id="x", role="agent_a")  # missing required `input`


def test_load_scenarios_finds_all_yaml_files_in_directory():
    scenarios = load_scenarios(SCENARIOS_DIR)

    assert len(scenarios) >= 1
    assert all(isinstance(s, ScenarioSpec) for s in scenarios)
    assert any(s.id == "list_projects" for s in scenarios)
