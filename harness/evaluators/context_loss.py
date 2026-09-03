"""Rule-based evaluator: did an orchestrator hand off complete, correct
context to the next agent?

v1 (day 9, default): flags keys that scenario.context_passed expects but
that are missing entirely, or present with the wrong value, in the
orchestrator's actual AgentResult.handoff_context — either way, the
receiving agent would work from wrong information. Extra keys the
orchestrator over-shares are ignored by default.

v2 (day 10, check_hallucinated_keys=True): additionally flags keys
present in the actual handoff context that were never part of
context_passed — context the orchestrator invented rather than lost.
Opt-in rather than the new default, mirroring how ToolCallSequenceEvaluator
keeps exact/subset/hallucination as selectable modes rather than folding
them together: "did the required context arrive?" and "did anything
extra get invented?" are different questions, and a scenario should be
free to check only the one it cares about.

Scenarios without context_passed set aren't handoff scenarios — this
evaluator trivially passes them, the same opt-in pattern
OutputFormatEvaluator uses for scenarios that don't care about output
shape.
"""

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


class ContextLossEvaluator:
    def __init__(self, check_hallucinated_keys: bool = False):
        self.check_hallucinated_keys = check_hallucinated_keys

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        expected = scenario.context_passed
        if expected is None:
            return EvaluationResult(passed=True, reasoning="scenario has no handoff context to check")

        actual = result.handoff_context or {}

        missing = [key for key in expected if key not in actual]
        mismatched = [key for key in expected if key in actual and actual[key] != expected[key]]
        hallucinated = [key for key in actual if key not in expected] if self.check_hallucinated_keys else []

        if not missing and not mismatched and not hallucinated:
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
        if hallucinated:
            problems.append(f"hallucinated keys {hallucinated!r} not in expected context {expected!r}")

        return EvaluationResult(passed=False, reasoning=f"context loss detected: {'; '.join(problems)}")
