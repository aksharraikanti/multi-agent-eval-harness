"""Day 23: regression gate policy — locking in that the LLM-judge is
advisory-only, permanently, and proving the advisory path can never
touch a process exit code no matter what the judge says.
"""

from harness.advisory import advisory_main, print_advisory_report, run_advisory_judge
from harness.cli import DEFAULT_EVALUATORS, evaluate_scenario
from harness.evaluators.base import EvaluationResult
from harness.llm_judge import LLMJudgeEvaluator
from harness.mock_agent import AgentResult
from harness.runner import SCENARIOS_DIR
from harness.schema import ScenarioSpec


class AlwaysFailsJudge:
    """A fake judge scripted to fail every scenario it sees — used to
    prove the advisory path stays advisory even in the worst case."""

    def evaluate(self, scenario, result) -> EvaluationResult:
        return EvaluationResult(passed=False, reasoning="the judge disapproves of everything")


class AlwaysPassesJudge:
    def evaluate(self, scenario, result) -> EvaluationResult:
        return EvaluationResult(passed=True, reasoning="looks fine to me")


# --- the policy itself: no LLMJudgeEvaluator in the blocking set --------

def test_default_evaluators_contains_no_llm_judge():
    # This is the actual policy: harness run's exit code (day 6, day 22's
    # CI step) comes entirely from DEFAULT_EVALUATORS. If an LLMJudgeEvaluator
    # ever ends up in this tuple, the judge becomes CI-blocking by
    # accident — this test exists to catch that the moment it happens.
    assert not any(isinstance(evaluator, LLMJudgeEvaluator) for evaluator in DEFAULT_EVALUATORS)


def test_default_evaluators_are_all_rule_based_and_free():
    # A rule-based evaluator never costs anything — every DEFAULT_EVALUATORS
    # entry should report cost_usd=None on every result, which is itself
    # evidence none of them are secretly making a paid API call.
    scenario = ScenarioSpec(id="x", role="agent_a", input="hello", expected_tool_calls=["x"])
    result = AgentResult(tool_calls=["x"])

    for evaluator in DEFAULT_EVALUATORS:
        outcome = evaluator.evaluate(scenario, result)
        assert outcome.cost_usd is None


# --- the advisory path never blocks, no matter the verdict ---------------

def test_advisory_reports_judge_failures_without_affecting_the_return_value():
    outcomes = run_advisory_judge([SCENARIOS_DIR], judge=AlwaysFailsJudge())

    # Every scenario genuinely fails under this judge...
    assert all(outcome.passed is False for outcome in outcomes)
    assert len(outcomes) > 0


def test_advisory_main_returns_zero_even_when_the_judge_fails_everything():
    exit_code = advisory_main([str(SCENARIOS_DIR)], judge=AlwaysFailsJudge())

    assert exit_code == 0


def test_advisory_main_returns_zero_when_the_judge_passes_everything_too():
    # Not just "0 because failures are ignored" — 0 regardless of the
    # verdict, because nothing in this path reads the verdict at all.
    exit_code = advisory_main([str(SCENARIOS_DIR)], judge=AlwaysPassesJudge())

    assert exit_code == 0


def test_advisory_report_prints_judge_verdicts(capsys):
    print_advisory_report(run_advisory_judge([SCENARIOS_DIR], judge=AlwaysFailsJudge()))

    output = capsys.readouterr().out
    assert "ADVISORY" in output
    assert "non-blocking" in output
    assert "[JUDGE FAIL]" in output


# --- the blocking path is genuinely independent of the advisory one -----

def test_blocking_evaluate_scenario_is_unaffected_by_a_failing_judge():
    # The real, CI-blocking evaluate_scenario() call for a scenario that
    # actually passes must still pass, even though a fake judge asked to
    # look at the exact same scenario separately fails it — these are
    # two totally independent calls, not one shared verdict.
    scenario = ScenarioSpec(
        id="ok",
        role="project_agent",
        input="What projects do I have access to?",
        expected_tool_calls=["list_projects"],
    )

    blocking_outcome = evaluate_scenario(scenario)
    advisory_outcome = evaluate_scenario(scenario, evaluators=(AlwaysFailsJudge(),))

    assert blocking_outcome.passed is True
    assert advisory_outcome.passed is False
