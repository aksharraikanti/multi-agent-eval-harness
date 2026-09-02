"""The single-scenario primitive: run one scenario against one agent
under one evaluator, print PASS/FAIL, return whether it passed.

This is what days 1-5 were built on and what most of the test suite
still exercises directly, since it's the simplest unit to test failure
modes against. The real, day-6 entry point for running the whole
scenario suite is `harness.cli` (installed as the `harness` command) —
it composes this same idea across every scenario and evaluator, with
per-scenario crash isolation and an agent registry instead of one
hardcoded agent.
"""

from pathlib import Path

from harness.evaluators import ToolCallSequenceEvaluator
from harness.mock_agent import CannedAgent
from harness.schema import ScenarioSpec

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
