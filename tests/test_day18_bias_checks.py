"""Day 18: judge bias checks.

These tests prove the checking machinery works — that check_verbosity_bias
and check_order_independence correctly distinguish a biased fake judge
from an honest one. They do NOT tell us whether the real Claude judge
is actually biased; that requires ANTHROPIC_API_KEY and running
`python -m harness.bias_checks` for real, which hasn't happened (see
docs/PLAN.md's day 18 entry).
"""

from harness.bias_checks import (
    BiasCheckResult,
    check_order_independence,
    check_verbosity_bias,
    VERBOSITY_PAIRS,
)
from harness.calibration_dataset import CALIBRATION_SET, LabeledExample
from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


class SubstringJudge:
    """An honest fake judge: PASS if the ticket key 'DEMO-42' literally
    appears in the output, FAIL otherwise. Correctness depends only on
    content, never on length — so it should show zero verbosity bias."""

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        passed = "DEMO-42" in result.output
        return EvaluationResult(passed=passed, reasoning="substring check")


class LengthImpressedJudge:
    """A deliberately biased fake judge: PASS if the output is long
    (regardless of content) OR contains the ticket key. Simulates a
    judge that gets talked into a pass by confident-sounding padding —
    exactly the failure mode check_verbosity_bias exists to catch."""

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        passed = "DEMO-42" in result.output or len(result.output) > 150
        return EvaluationResult(passed=passed, reasoning="length-impressed check")


# --- check_verbosity_bias --------------------------------------------------

def test_honest_judge_shows_no_verbosity_bias():
    result = check_verbosity_bias(VERBOSITY_PAIRS, SubstringJudge())

    assert isinstance(result, BiasCheckResult)
    assert result.consistency_rate == 1.0
    assert result.flagged == []


def test_biased_judge_is_flagged_on_the_pair_where_it_matters():
    result = check_verbosity_bias(VERBOSITY_PAIRS, LengthImpressedJudge())

    # The "key present" pair: both short and verbose contain DEMO-42, so
    # the biased judge happens to agree on that one too (passes both,
    # for different reasons). The "key absent" pair is where the bias
    # actually shows: short answer correctly fails, padded answer
    # wrongly passes purely on length.
    assert "ticket_key_absent_short_vs_padded" in result.flagged
    assert result.consistency_rate < 1.0


def test_verbosity_bias_result_reports_correct_totals():
    result = check_verbosity_bias(VERBOSITY_PAIRS, LengthImpressedJudge())

    assert result.total == len(VERBOSITY_PAIRS)
    assert result.consistent + len(result.flagged) == result.total


def test_verbosity_pairs_are_genuinely_paired_on_correctness():
    # Sanity check on the fixtures themselves: within each pair, the
    # short and verbose outputs must be equally correct against a
    # ground-truth substring check, or the pair doesn't actually isolate
    # verbosity as the variable.
    for pair in VERBOSITY_PAIRS:
        short_has_key = "DEMO-42" in pair.short_result.output
        verbose_has_key = "DEMO-42" in pair.verbose_result.output
        assert short_has_key == verbose_has_key, f"{pair.name} isn't correctness-matched"


# --- check_order_independence ----------------------------------------------

class StatelessScriptedJudge:
    """A pure lookup by scenario.id — structurally incapable of caring
    what order it's called in, since it has no memory between calls."""

    def __init__(self, verdicts: dict[str, bool]):
        self._verdicts = verdicts

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        return EvaluationResult(passed=self._verdicts[scenario.id], reasoning="scripted")


def test_stateless_judge_is_order_independent():
    verdicts = {example.scenario.id: example.human_label for example in CALIBRATION_SET}
    judge = StatelessScriptedJudge(verdicts)

    result = check_order_independence(CALIBRATION_SET, judge)

    assert result.flagged == []
    assert result.consistency_rate == 1.0


class PositionLeakingJudge:
    """A deliberately broken fake judge that DOES have memory: it flips
    its verdict on the 2nd example it ever sees, simulating a bug where
    state leaked across calls (e.g. a naive prompt cache keyed wrong).
    Exists only to prove check_order_independence would actually catch
    that if it happened — the real LLMJudgeEvaluator has no such state."""

    def __init__(self, verdicts: dict[str, bool]):
        self._verdicts = verdicts
        self._call_count = 0

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        self._call_count += 1
        base_verdict = self._verdicts[scenario.id]
        if self._call_count == 2:
            base_verdict = not base_verdict
        return EvaluationResult(passed=base_verdict, reasoning="leaky")


def test_order_dependent_judge_is_flagged():
    examples = CALIBRATION_SET[:5]
    verdicts = {example.scenario.id: example.human_label for example in examples}

    result = check_order_independence(examples, PositionLeakingJudge(verdicts))

    assert result.flagged != []
    assert result.consistency_rate < 1.0


def test_order_independence_result_reports_correct_totals():
    verdicts = {example.scenario.id: example.human_label for example in CALIBRATION_SET}
    result = check_order_independence(CALIBRATION_SET, StatelessScriptedJudge(verdicts))

    assert result.total == len(CALIBRATION_SET)
    assert result.consistent == len(CALIBRATION_SET)
