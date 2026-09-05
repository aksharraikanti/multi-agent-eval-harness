"""Day 16: LLM-judge scorer v1.

Most tests here use a fake, injected client to test prompt construction
and verdict parsing without a network call, an API key, or the
anthropic package — the same reason `client=` exists on
LLMJudgeEvaluator in the first place. One test makes a real call and
skips cleanly when ANTHROPIC_API_KEY isn't set, so the default suite
stays runnable with no secrets.
"""

import pytest

from harness.evaluators.base import EvaluationResult
from harness.llm_judge import anthropic_is_available, LLMJudgeEvaluator
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec

NO_RUBRIC_SCENARIO = ScenarioSpec(id="x", role="agent_a", input="hello")

RUBRIC_SCENARIO = ScenarioSpec(
    id="create_ticket",
    role="ticket_agent",
    input="Create a ticket in the DEMO project titled 'Fix login bug'",
    success_criteria="The agent must call create_ticket and the output must contain the new ticket's key.",
)


class FakeMessage:
    def __init__(self, text: str):
        self.content = [FakeTextBlock(text)]


class FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class FakeMessagesAPI:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return FakeMessage(self._response_text)


class FakeAnthropicClient:
    def __init__(self, response_text: str):
        self.messages = FakeMessagesAPI(response_text)


def test_scenario_without_success_criteria_trivially_passes():
    fake_client = FakeAnthropicClient("this should never be called")
    evaluator = LLMJudgeEvaluator(client=fake_client)
    result = AgentResult(output="anything")

    outcome = evaluator.evaluate(NO_RUBRIC_SCENARIO, result)

    assert outcome.passed is True
    assert fake_client.messages.last_call_kwargs is None  # never actually called


def test_pass_verdict_maps_to_passed_true():
    fake_client = FakeAnthropicClient("PASS: the ticket key DEMO-42 appears in the output.")
    evaluator = LLMJudgeEvaluator(client=fake_client)
    result = AgentResult(tool_calls=["create_ticket"], output="Created DEMO-42.")

    outcome = evaluator.evaluate(RUBRIC_SCENARIO, result)

    assert isinstance(outcome, EvaluationResult)
    assert outcome.passed is True
    assert "DEMO-42" in outcome.reasoning


def test_fail_verdict_maps_to_passed_false():
    fake_client = FakeAnthropicClient("FAIL: no ticket key is present in the output.")
    evaluator = LLMJudgeEvaluator(client=fake_client)
    result = AgentResult(tool_calls=["create_ticket"], output="Ticket created.")

    outcome = evaluator.evaluate(RUBRIC_SCENARIO, result)

    assert outcome.passed is False
    assert "no ticket key" in outcome.reasoning


def test_verdict_matching_is_case_insensitive():
    fake_client = FakeAnthropicClient("pass: lowercase verdict should still count.")
    evaluator = LLMJudgeEvaluator(client=fake_client)

    outcome = evaluator.evaluate(RUBRIC_SCENARIO, AgentResult(output="x"))

    assert outcome.passed is True


def test_prompt_includes_the_rubric_and_the_agents_actual_output():
    fake_client = FakeAnthropicClient("PASS: fine.")
    evaluator = LLMJudgeEvaluator(client=fake_client)
    result = AgentResult(tool_calls=["create_ticket"], output="Created DEMO-42.")

    evaluator.evaluate(RUBRIC_SCENARIO, result)

    prompt = fake_client.messages.last_call_kwargs["messages"][0]["content"]
    assert RUBRIC_SCENARIO.success_criteria in prompt
    assert "Created DEMO-42." in prompt
    assert "create_ticket" in prompt


def test_uses_the_configured_model():
    fake_client = FakeAnthropicClient("PASS: fine.")
    evaluator = LLMJudgeEvaluator(model="claude-test-model", client=fake_client)

    evaluator.evaluate(RUBRIC_SCENARIO, AgentResult(output="x"))

    assert fake_client.messages.last_call_kwargs["model"] == "claude-test-model"


# --- real API call, skipped without credentials --------------------------

@pytest.mark.skipif(not anthropic_is_available(), reason="requires ANTHROPIC_API_KEY and the anthropic package")
def test_real_judge_call_against_a_real_model():
    evaluator = LLMJudgeEvaluator()
    result = AgentResult(tool_calls=["create_ticket"], output="Created DEMO-42.")

    outcome = evaluator.evaluate(RUBRIC_SCENARIO, result)

    assert outcome.passed is True
    assert outcome.reasoning
