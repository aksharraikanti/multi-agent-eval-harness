"""Day 17: judge calibration machinery.

These tests use a fake judge scripted to return specific verdicts per
example name — the point isn't to test the real Claude judge here
(that needs a real API key, see test_day16_llm_judge.py), it's to prove
calibrate() correctly measures agreement between whatever a judge says
and the hand labels, and correctly tells a good judge from a lazy one.
"""

from harness.calibration import calibrate, CalibrationResult, is_calibrated
from harness.calibration_dataset import CALIBRATION_SET, LabeledExample
from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


class ScriptedJudge:
    """A fake judge whose verdict per example is controlled directly by
    the test, keyed by scenario.id (each LabeledExample stamps its own
    name onto scenario.id — see calibration_dataset.py)."""

    def __init__(self, verdicts: dict[str, bool]):
        self._verdicts = verdicts

    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        passed = self._verdicts[scenario.id]
        return EvaluationResult(passed=passed, reasoning="scripted")


def _example(name: str, human_label: bool) -> LabeledExample:
    scenario = ScenarioSpec(id=name, role="test_agent", input="x", success_criteria="irrelevant for this test")
    return LabeledExample(name=name, scenario=scenario, result=AgentResult(output="x"), human_label=human_label)


def test_perfect_judge_gets_full_agreement():
    examples = [_example("a", True), _example("b", False), _example("c", True)]
    judge = ScriptedJudge({"a": True, "b": False, "c": True})

    result = calibrate(examples, judge)

    assert isinstance(result, CalibrationResult)
    assert result.total == 3
    assert result.agreements == 3
    assert result.disagreements == []
    assert result.agreement_rate == 1.0


def test_partial_agreement_lists_the_disagreeing_examples_by_name():
    examples = [_example("a", True), _example("b", False), _example("c", True)]
    judge = ScriptedJudge({"a": True, "b": True, "c": False})  # b and c both wrong

    result = calibrate(examples, judge)

    assert result.agreements == 1
    assert set(result.disagreements) == {"b", "c"}
    assert result.agreement_rate == 1 / 3


def test_always_pass_judge_only_agrees_on_the_true_labeled_examples():
    # A lazy judge that just says PASS every time should score exactly
    # as well as "fraction of examples labeled True" — no better.
    examples = [_example("a", True), _example("b", False), _example("c", True), _example("d", False)]
    lazy_judge = ScriptedJudge({"a": True, "b": True, "c": True, "d": True})

    result = calibrate(examples, lazy_judge)

    assert result.agreement_rate == 0.5


def test_agreement_rate_on_empty_set_is_zero_not_a_crash():
    result = calibrate([], ScriptedJudge({}))

    assert result.total == 0
    assert result.agreement_rate == 0.0


def test_is_calibrated_uses_the_default_threshold():
    good_result = CalibrationResult(total=10, agreements=9)
    bad_result = CalibrationResult(total=10, agreements=5)

    assert is_calibrated(good_result) is True
    assert is_calibrated(bad_result) is False


def test_is_calibrated_accepts_a_custom_threshold():
    result = CalibrationResult(total=10, agreements=7)

    assert is_calibrated(result, threshold=0.7) is True
    assert is_calibrated(result, threshold=0.71) is False


# --- the real hand-labeled dataset ------------------------------------

def test_calibration_set_has_at_least_ten_examples():
    # docs/PLAN.md's day 17 calls for 10-15 hand-labeled examples.
    assert 10 <= len(CALIBRATION_SET) <= 15


def test_calibration_set_names_are_unique():
    names = [example.name for example in CALIBRATION_SET]
    assert len(names) == len(set(names))


def test_calibration_set_is_not_all_one_label():
    # A dataset that's all True or all False can't actually distinguish
    # a good judge from one that always agrees with itself.
    labels = {example.human_label for example in CALIBRATION_SET}
    assert labels == {True, False}


def test_calibrate_runs_against_the_real_dataset_with_a_scripted_judge():
    # Doesn't need a real API key — just proves calibrate() runs
    # end-to-end against the actual CALIBRATION_SET (not a toy list),
    # using a judge scripted to agree with every label.
    verdicts = {example.scenario.id: example.human_label for example in CALIBRATION_SET}
    judge = ScriptedJudge(verdicts)

    result = calibrate(CALIBRATION_SET, judge)

    assert result.agreement_rate == 1.0
    assert is_calibrated(result) is True
