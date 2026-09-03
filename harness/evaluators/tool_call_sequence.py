"""Rule-based evaluator: did the agent make the right tool calls?

Pulled out of the runner (days 1-3 had this check inline) so it can be
reused and tested on its own. Day 7 adds a third mode instead of a new
evaluator class, since it's the same underlying question — "were the
tool calls correct?" — just checked from the opposite direction: exact
and subset both ask whether the *required* calls happened; hallucination
asks whether any call happened that *shouldn't* have. Notably, subset
mode explicitly allows extra calls, so it alone would never catch a
hallucinated one — that's what makes hallucination mode a genuinely
separate check rather than a stricter subset.
"""

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec

VALID_MODES = ("exact", "subset", "hallucination")


class ToolCallSequenceEvaluator:
    """Checks an agent's tool calls against a scenario's tool-call fields.

    mode="exact" (default): actual calls must equal expected_tool_calls,
    including order. The strict check — use it when the workflow order
    matters (e.g. list_projects must happen before create_ticket).

    mode="subset": every expected_tool_calls entry must appear somewhere
    in the actual calls; extra calls and a different order are allowed.
    The loose check — use it when only "did the necessary calls happen"
    matters, not the exact sequence.

    mode="hallucination": every actual call must appear in the allow-list
    (scenario.allowed_tool_calls, or expected_tool_calls if that's unset).
    Any actual call outside the allow-list fails the check. Use it
    alongside subset mode when order flexibility is fine but an
    unauthorized call (e.g. a destructive action during a read-only
    query) still needs to be caught.
    """

    def __init__(self, mode: str = "exact"):
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown mode: {mode!r} (expected one of {VALID_MODES})")
        self.mode = mode

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        if self.mode == "hallucination":
            return self._evaluate_hallucination(scenario, result)
        return self._evaluate_sequence(scenario, result)

    def _evaluate_sequence(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
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

    def _evaluate_hallucination(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        allowed = (
            scenario.allowed_tool_calls
            if scenario.allowed_tool_calls is not None
            else scenario.expected_tool_calls
        )
        hallucinated = [call for call in result.tool_calls if call not in allowed]

        if not hallucinated:
            return EvaluationResult(
                passed=True,
                reasoning=f"no hallucinated tool calls (allowed: {allowed!r})",
            )
        return EvaluationResult(
            passed=False,
            reasoning=f"agent called {hallucinated!r}, not in allowed set {allowed!r}",
        )
