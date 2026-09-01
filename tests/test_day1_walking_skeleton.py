"""Day 1: prove the walking skeleton actually catches pass and fail cases."""

from harness.mock_agent import AgentResult, CannedAgent
from harness.runner import run_scenario, SCENARIOS_DIR
from harness.scenario_loader import load_scenario


def test_correct_agent_passes():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    agent = CannedAgent({
        "What projects do I have access to?": AgentResult(tool_calls=["list_projects"]),
    })

    assert run_scenario(scenario, agent) is True


def test_wrong_tool_calls_fail():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    agent = CannedAgent({
        # Wrong tool entirely — the harness must catch this, not just
        # "an agent ran and produced output."
        "What projects do I have access to?": AgentResult(tool_calls=["search_docs"]),
    })

    assert run_scenario(scenario, agent) is False


def test_missing_tool_call_fails():
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")
    agent = CannedAgent({
        # Agent answers from memory without calling any tool.
        "What projects do I have access to?": AgentResult(tool_calls=[]),
    })

    assert run_scenario(scenario, agent) is False
