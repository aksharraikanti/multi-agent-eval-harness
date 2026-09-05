"""LLM-judge scorer v1: grade an open-ended scenario against its
success_criteria using a real Claude API call.

Wired as an evaluator so it fits the same EvaluationResult interface as
every rule-based evaluator (days 4/5/9/10) — PASS/FAIL from the judge
maps directly to passed=True/False, and the judge's own explanation
becomes the reasoning.

Deliberately NOT wired into DEFAULT_EVALUATORS (harness/cli.py) and not
part of the default scenario suite: per the project's own ground rules
(docs/PLAN.md), the judge is never CI-blocking even after calibration
(day 17), and this is day 1 of that story — no calibration has run yet.
Requires ANTHROPIC_API_KEY and the anthropic package; the client is
injectable specifically so the prompt-construction and verdict-parsing
logic can be tested without either, keeping the default test suite
runnable offline with no secrets.
"""

import os

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec

# claude-haiku-4-5 — cheap and fast, plenty for a rubric-grading task.
# Was claude-3-5-haiku-latest until day 21: that model id doesn't appear
# in current Anthropic pricing at all and looks retired. Checked via the
# claude-api skill rather than trusting a stale training-data model name.
JUDGE_MODEL = "claude-haiku-4-5"

# $/million tokens, Claude Haiku 4.5, confirmed via the claude-api skill
# on 2026-09-01 (cached pricing table dated 2026-06-24). Verify against
# Anthropic's published pricing before trusting cost figures long after
# that date — prices change and this constant won't update itself.
JUDGE_INPUT_COST_PER_MILLION = 1.00
JUDGE_OUTPUT_COST_PER_MILLION = 5.00

JUDGE_SYSTEM_PROMPT = (
    "You are grading whether an AI agent's response satisfies a rubric. "
    'Respond with exactly one line: "PASS: <one-sentence reason>" or '
    '"FAIL: <one-sentence reason>". Nothing else.'
)


def anthropic_is_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class LLMJudgeEvaluator:
    """Grades a scenario's output against its success_criteria.

    Scenarios without success_criteria trivially pass — there's nothing
    to judge against, the same opt-in pattern every other evaluator here
    uses for a field it doesn't care about.
    """

    def __init__(self, model: str = JUDGE_MODEL, client=None):
        self._model = model
        self._client = client

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        if scenario.success_criteria is None:
            return EvaluationResult(passed=True, reasoning="scenario has no success_criteria to judge")

        prompt = (
            f"Rubric: {scenario.success_criteria}\n\n"
            f"Agent's tool calls: {result.tool_calls!r}\n"
            f"Agent's output: {result.output!r}\n\n"
            "Does this satisfy the rubric?"
        )

        response = self._get_client().messages.create(
            model=self._model,
            max_tokens=200,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        verdict = response.content[0].text.strip()
        cost_usd = self._compute_cost(response.usage)

        return EvaluationResult(passed=verdict.upper().startswith("PASS"), reasoning=verdict, cost_usd=cost_usd)

    def _compute_cost(self, usage) -> float:
        input_cost = usage.input_tokens * JUDGE_INPUT_COST_PER_MILLION / 1_000_000
        output_cost = usage.output_tokens * JUDGE_OUTPUT_COST_PER_MILLION / 1_000_000
        return input_cost + output_cost
