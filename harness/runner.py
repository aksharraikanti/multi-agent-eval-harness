"""Day 1-2: load scenarios (now via the pydantic schema + YAML loader),
run one mock agent, check its tool calls against what's expected, print
PASS/FAIL.

Still the smallest reasonable end-to-end slice. A real runner CLI that
walks a whole directory and applies pluggable evaluators lands day 6.
"""

import sys
from pathlib import Path

from harness.mock_agent import AgentResult, CannedAgent
from harness.schema import ScenarioSpec
from harness.scenario_loader import load_scenario

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def run_scenario(scenario: ScenarioSpec, agent: CannedAgent) -> bool:
    """Run one scenario against one agent and return whether it passed."""
    result = agent.run(scenario.input)
    passed = result.tool_calls == scenario.expected_tool_calls

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {scenario.id}")
    if not passed:
        print(f"    expected tool calls: {scenario.expected_tool_calls}")
        print(f"    actual tool calls:   {result.tool_calls}")

    return passed


def main() -> int:
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.yaml")

    agent = CannedAgent({
        "What projects do I have access to?": AgentResult(
            tool_calls=["list_projects"],
            output="You have access to 2 projects: DEMO, TEST",
        ),
    })

    passed = run_scenario(scenario, agent)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
