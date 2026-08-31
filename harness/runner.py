"""Day 1 walking skeleton: load one scenario, run one mock agent, check its
tool calls against what the scenario expects, print PASS/FAIL.

This is deliberately the smallest possible end-to-end slice. Everything
after day 1 (schema, more evaluators, handoff detection, mock tool
servers, a real runner CLI over a whole directory of scenarios) widens
this same path rather than replacing it.
"""

import json
import sys
from pathlib import Path

from harness.mock_agent import AgentResult, CannedAgent

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def load_scenario(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def run_scenario(scenario: dict, agent: CannedAgent) -> bool:
    """Run one scenario against one agent and return whether it passed."""
    result = agent.run(scenario["input"])
    passed = result.tool_calls == scenario["expected_tool_calls"]

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {scenario['id']}")
    if not passed:
        print(f"    expected tool calls: {scenario['expected_tool_calls']}")
        print(f"    actual tool calls:   {result.tool_calls}")

    return passed


def main() -> int:
    scenario = load_scenario(SCENARIOS_DIR / "list_projects.json")

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
