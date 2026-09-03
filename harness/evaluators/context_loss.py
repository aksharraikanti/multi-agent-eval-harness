"""Rule-based evaluator: did an orchestrator hand off complete, correct
context to the next agent?

v1 (day 9): flags keys that scenario.context_passed expects but that are
missing entirely, or present with the wrong value, in the orchestrator's
actual AgentResult.handoff_context — either way, the receiving agent
would work from wrong information. v2 (day 10) adds the opposite check:
keys the orchestrator invented that were never part of context_passed;
v1 deliberately ignores extra keys, so it won't flag them.

Scenarios without context_passed set aren't handoff scenarios — this
evaluator trivially passes them, the same opt-in pattern
OutputFormatEvaluator uses for scenarios that don't care about output
shape.
"""

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


class ContextLossEvaluator:
    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        expected = scenario.context_passed
        if expected is None:
            return EvaluationResult(passed=True, reasoning="scenario has no handoff context to check")

        actual = result.handoff_context or {}

        missing = [key for key in expected if key not in actual]
        mismatched = [key for key in expected if key in actual and actual[key] != expected[key]]

        if not missing and not mismatched:
            return EvaluationResult(
                passed=True,
                reasoning=f"handoff context matches expected {expected!r}",
            )

        problems = []
        if missing:
            problems.append(f"missing keys {missing!r}")
        if mismatched:
            details = {key: (expected[key], actual[key]) for key in mismatched}
            problems.append(f"mismatched values (expected, actual) {details!r}")

        return EvaluationResult(passed=False, reasoning=f"context loss detected: {'; '.join(problems)}")
