"""Days 1-4: load a scenario, run one mock agent, evaluate its tool calls
with the rule-based evaluator, print PASS/FAIL.

Still the smallest reasonable end-to-end slice. A real runner CLI that
walks a whole directory and applies multiple pluggable evaluators lands
day 6.
"""

import sys
from pathlib import Path

from harness.evaluators import ToolCallSequenceEvaluator
from harness.mock_agent import AgentResult, CannedAgent
from harness.schema import ScenarioSpec
from harness.scenario_loader import load_scenario

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

DEFAULT_EVALUATOR = ToolCallSequenceEvaluator(mode="exact")


def run_scenario(scenario: ScenarioSpec, agent: CannedAgent, evaluator=DEFAULT_EVALUATOR) -> bool:
    """Run one scenario against one agent and return whether it passed."""
    result = agent.run(scenario.input)
    outcome = evaluator.evaluate(scenario, result)

    status = "PASS" if outcome.passed else "FAIL"
    print(f"[{status}] {scenario.id}")
    if not outcome.passed:
        print(f"    {outcome.reasoning}")

    return outcome.passed


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
