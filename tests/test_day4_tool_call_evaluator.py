"""Day 4: rule-based tool-call-sequence evaluator, exact and subset modes."""

import pytest

from harness.evaluators import EvaluationResult, ToolCallSequenceEvaluator
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec

SCENARIO = ScenarioSpec(
    id="two-call",
    role="ticket_agent",
    input="irrelevant for this test",
    expected_tool_calls=["list_projects", "create_ticket"],
)


def test_exact_mode_passes_on_identical_sequence():
    evaluator = ToolCallSequenceEvaluator(mode="exact")
    result = AgentResult(tool_calls=["list_projects", "create_ticket"])

    outcome = evaluator.evaluate(SCENARIO, result)

    assert isinstance(outcome, EvaluationResult)
    assert outcome.passed is True


def test_exact_mode_fails_on_different_order():
    evaluator = ToolCallSequenceEvaluator(mode="exact")
    result = AgentResult(tool_calls=["create_ticket", "list_projects"])

    assert evaluator.evaluate(SCENARIO, result).passed is False


def test_exact_mode_fails_on_extra_call():
    evaluator = ToolCallSequenceEvaluator(mode="exact")
    result = AgentResult(tool_calls=["list_projects", "create_ticket", "add_comment"])

    assert evaluator.evaluate(SCENARIO, result).passed is False


def test_subset_mode_passes_regardless_of_order():
    evaluator = ToolCallSequenceEvaluator(mode="subset")
    result = AgentResult(tool_calls=["create_ticket", "list_projects"])

    assert evaluator.evaluate(SCENARIO, result).passed is True


def test_subset_mode_passes_with_extra_calls():
    evaluator = ToolCallSequenceEvaluator(mode="subset")
    result = AgentResult(tool_calls=["list_projects", "add_comment", "create_ticket"])

    assert evaluator.evaluate(SCENARIO, result).passed is True


def test_subset_mode_still_fails_if_a_required_call_is_missing():
    evaluator = ToolCallSequenceEvaluator(mode="subset")
    result = AgentResult(tool_calls=["create_ticket"])  # list_projects never happened

    assert evaluator.evaluate(SCENARIO, result).passed is False


def test_failing_evaluation_explains_what_was_expected_and_what_happened():
    evaluator = ToolCallSequenceEvaluator(mode="exact")
    result = AgentResult(tool_calls=["create_ticket"])

    outcome = evaluator.evaluate(SCENARIO, result)

    assert "list_projects" in outcome.reasoning
    assert "create_ticket" in outcome.reasoning


def test_unknown_mode_is_rejected_at_construction():
    with pytest.raises(ValueError):
        ToolCallSequenceEvaluator(mode="fuzzy")
