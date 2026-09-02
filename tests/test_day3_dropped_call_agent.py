"""Day 3: a mock agent with an injected failure mode — it drops a
required tool call from an otherwise-correct sequence.
"""

from harness.mock_agent import AgentResult, CannedAgent, DropsToolCallAgent
from harness.runner import run_scenario, SCENARIOS_DIR
from harness.scenario_loader import load_scenario

INPUT_TEXT = "Create a ticket in the DEMO project titled 'Fix login bug'"
CORRECT_SCRIPT = {
    INPUT_TEXT: AgentResult(
        tool_calls=["list_projects", "create_ticket"],
        output="Created DEMO-42.",
    ),
}


def test_correct_agent_passes_the_multi_call_scenario():
    scenario = load_scenario(SCENARIOS_DIR / "create_ticket.yaml")
    agent = CannedAgent(CORRECT_SCRIPT)

    assert run_scenario(scenario, agent) is True


def test_dropped_call_agent_fails_the_scenario():
    scenario = load_scenario(SCENARIOS_DIR / "create_ticket.yaml")
    # Same underlying script as the correct agent — the only difference is
    # the wrapper skipping the verification step.
    agent = DropsToolCallAgent(CORRECT_SCRIPT, drop="list_projects")

    assert run_scenario(scenario, agent) is False


def test_dropped_call_agent_only_removes_the_named_call():
    agent = DropsToolCallAgent(CORRECT_SCRIPT, drop="list_projects")

    result = agent.run(INPUT_TEXT)

    assert result.tool_calls == ["create_ticket"]
    assert result.output == "Created DEMO-42."


def test_underlying_script_is_unmodified():
    # The wrapper filters at call time — it must not mutate the script it
    # wraps, so the same CORRECT_SCRIPT can back both a correct agent and
    # a dropped-call agent in the same test module without interference.
    agent = DropsToolCallAgent(CORRECT_SCRIPT, drop="list_projects")
    agent.run(INPUT_TEXT)

    assert CORRECT_SCRIPT[INPUT_TEXT].tool_calls == ["list_projects", "create_ticket"]
