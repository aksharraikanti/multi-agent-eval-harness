"""Rule-based evaluator: did the agent make the right tool calls?

Pulled out of the runner (days 1-3 had this check inline) so it can be
reused, tested on its own, and extended in day 7 with a hallucination-
detection mode — without the runner needing to change.
"""

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec

VALID_MODES = ("exact", "subset")


class ToolCallSequenceEvaluator:
    """Checks an agent's tool calls against a scenario's expected_tool_calls.

    mode="exact" (default): actual calls must equal expected calls,
    including order. The strict check — use it when the workflow order
    matters (e.g. list_projects must happen before create_ticket).

    mode="subset": every expected call must appear somewhere in the
    actual calls; extra calls and a different order are allowed. The
    loose check — use it when only "did the necessary calls happen"
    matters, not the exact sequence.
    """

    def __init__(self, mode: str = "exact"):
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown mode: {mode!r} (expected one of {VALID_MODES})")
        self.mode = mode

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        expected = scenario.expected_tool_calls
        actual = result.tool_calls

        if self.mode == "exact":
            passed = actual == expected
        else:  # subset
            passed = all(call in actual for call in expected)

        if passed:
            return EvaluationResult(
                passed=True,
                reasoning=f"tool calls satisfied expected {expected!r} ({self.mode} match)",
            )
        return EvaluationResult(
            passed=False,
            reasoning=(
                f"expected tool calls {expected!r} not satisfied by actual "
                f"{actual!r} ({self.mode} match)"
            ),
        )
