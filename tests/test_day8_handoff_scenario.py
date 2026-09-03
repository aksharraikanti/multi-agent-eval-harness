"""Day 8: the two-agent handoff scenario spec.

This day doesn't build the context-loss detector yet (days 9-10) — it
establishes the data model and a real example: a scenario that names a
handoff target and the context that should cross it, and an orchestrator
mock agent whose AgentResult actually carries that handoff context. Days
9-10 diff the two.
"""

from harness.agent_registry import get_agent
from harness.mock_agent import AgentResult
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario
from harness.schema import ScenarioSpec


def test_agent_result_handoff_context_defaults_to_none():
    result = AgentResult(tool_calls=["x"], output="y")

    assert result.handoff_context is None


def test_agent_result_can_carry_handoff_context():
    result = AgentResult(handoff_context={"project_key": "DEMO"})

    assert result.handoff_context == {"project_key": "DEMO"}


def test_pre_day8_scenarios_still_validate_without_handoff_fields():
    # No scenario written before today set handoff_to/context_passed —
    # confirms the day-2 promise that these fields never force a migration.
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")

    assert scenario.handoff_to is None
    assert scenario.context_passed is None


def test_handoff_scenario_file_loads_with_both_fields_set():
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")

    assert isinstance(scenario, ScenarioSpec)
    assert scenario.role == "orchestrator"
    assert scenario.handoff_to == "ticket_agent"
    assert scenario.context_passed == {
        "project_key": "DEMO",
        "title": "Fix login bug",
        "reporter_email": "user@example.com",
    }


def test_registered_orchestrator_produces_the_handoff_context_the_scenario_expects():
    # Ground truth check: the mock orchestrator's actual handoff_context
    # matches what the scenario says should be passed. This is the "happy
    # path" case the day-9/10 detector will need to correctly pass, not
    # just correctly fail on injected drift.
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    agent = get_agent(scenario.role)

    result = agent.run(scenario.input)

    assert result.handoff_context == scenario.context_passed


def test_single_agent_scenarios_have_no_handoff_context_from_their_agent():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    agent = get_agent(scenario.role)

    result = agent.run(scenario.input)

    assert result.handoff_context is None
