"""Day 9: context-loss detector v1 — missing/mismatched keys in a
handoff, deliberately blind to extra keys (that's day 10)."""

from harness.agent_registry import get_agent
from harness.evaluators import ContextLossEvaluator
from harness.mock_agent import (
    AgentResult,
    DropsContextKeyAgent,
    DropsToolCallAgent,
    HallucinatesToolCallAgent,
)
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario
from harness.schema import ScenarioSpec

HANDOFF_CREATE_TICKET_SCRIPT = {
    "Create a ticket in the DEMO project titled 'Fix login bug' and notify the reporter": AgentResult(
        tool_calls=["parse_request"],
        output="Handing off to ticket_agent.",
        handoff_context={
            "project_key": "DEMO",
            "title": "Fix login bug",
            "reporter_email": "user@example.com",
        },
    ),
}

NO_HANDOFF_SCENARIO = ScenarioSpec(id="x", role="agent_a", input="hello")

HANDOFF_SCENARIO = ScenarioSpec(
    id="handoff-example",
    role="orchestrator",
    input="hello",
    handoff_to="worker_agent",
    context_passed={"project_key": "DEMO", "title": "Fix login bug"},
)


def test_scenario_without_context_passed_trivially_passes():
    evaluator = ContextLossEvaluator()
    result = AgentResult(handoff_context={"anything": "goes"})

    assert evaluator.evaluate(NO_HANDOFF_SCENARIO, result).passed is True


def test_exact_match_passes():
    evaluator = ContextLossEvaluator()
    result = AgentResult(handoff_context={"project_key": "DEMO", "title": "Fix login bug"})

    assert evaluator.evaluate(HANDOFF_SCENARIO, result).passed is True


def test_missing_key_fails():
    evaluator = ContextLossEvaluator()
    result = AgentResult(handoff_context={"project_key": "DEMO"})  # title dropped

    outcome = evaluator.evaluate(HANDOFF_SCENARIO, result)

    assert outcome.passed is False
    assert "title" in outcome.reasoning


def test_all_context_dropped_fails_with_every_key_missing():
    evaluator = ContextLossEvaluator()
    result = AgentResult(handoff_context=None)

    outcome = evaluator.evaluate(HANDOFF_SCENARIO, result)

    assert outcome.passed is False
    assert "project_key" in outcome.reasoning
    assert "title" in outcome.reasoning


def test_mismatched_value_fails():
    evaluator = ContextLossEvaluator()
    result = AgentResult(handoff_context={"project_key": "TEST", "title": "Fix login bug"})

    outcome = evaluator.evaluate(HANDOFF_SCENARIO, result)

    assert outcome.passed is False
    assert "project_key" in outcome.reasoning
    assert "DEMO" in outcome.reasoning  # expected value shows up in the explanation
    assert "TEST" in outcome.reasoning  # so does the actual, wrong, value


def test_v1_ignores_extra_keys_that_werent_expected():
    # By design: hallucinated-key detection is day 10's job. v1 only
    # checks what was expected, so an orchestrator that over-shares
    # (passes something extra alongside everything required) still passes.
    evaluator = ContextLossEvaluator()
    result = AgentResult(
        handoff_context={"project_key": "DEMO", "title": "Fix login bug", "extra": "unexpected"}
    )

    assert evaluator.evaluate(HANDOFF_SCENARIO, result).passed is True


# --- DropsContextKeyAgent -------------------------------------------------

def test_drops_context_key_agent_removes_only_the_named_key():
    script = {
        "hello": AgentResult(
            tool_calls=["parse_request"],
            output="ok",
            handoff_context={"project_key": "DEMO", "title": "Fix login bug"},
        )
    }
    agent = DropsContextKeyAgent(script, drop_key="title")

    result = agent.run("hello")

    assert result.handoff_context == {"project_key": "DEMO"}
    assert result.tool_calls == ["parse_request"]  # untouched
    assert result.output == "ok"


def test_drops_context_key_agent_is_a_noop_when_no_handoff_context():
    script = {"hello": AgentResult(tool_calls=["x"], output="ok")}
    agent = DropsContextKeyAgent(script, drop_key="title")

    result = agent.run("hello")

    assert result.handoff_context is None


# --- regression: earlier wrapper agents must preserve handoff_context ----

def test_drops_tool_call_agent_preserves_handoff_context():
    # DropsToolCallAgent (day 3) predates handoff_context (day 8) and
    # originally rebuilt AgentResult without it — silently wiping any
    # handoff context whenever it wrapped an orchestrator, not just the
    # tool call it was meant to drop. Fixed alongside this evaluator.
    script = {
        "hello": AgentResult(
            tool_calls=["parse_request", "extra_call"],
            output="ok",
            handoff_context={"project_key": "DEMO"},
        )
    }
    agent = DropsToolCallAgent(script, drop="extra_call")

    result = agent.run("hello")

    assert result.handoff_context == {"project_key": "DEMO"}


def test_hallucinates_tool_call_agent_preserves_handoff_context():
    script = {
        "hello": AgentResult(
            tool_calls=["parse_request"],
            output="ok",
            handoff_context={"project_key": "DEMO"},
        )
    }
    agent = HallucinatesToolCallAgent(script, hallucinate="delete_ticket")

    result = agent.run("hello")

    assert result.handoff_context == {"project_key": "DEMO"}


# --- end to end: real scenario + real agents -----------------------------

def test_registered_orchestrator_passes_context_loss_check():
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    agent = get_agent(scenario.role)
    evaluator = ContextLossEvaluator()

    result = agent.run(scenario.input)

    assert evaluator.evaluate(scenario, result).passed is True


def test_dropped_context_key_agent_fails_the_real_handoff_scenario():
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    faulty_agent = DropsContextKeyAgent(HANDOFF_CREATE_TICKET_SCRIPT, drop_key="reporter_email")
    evaluator = ContextLossEvaluator()

    result = faulty_agent.run(scenario.input)
    outcome = evaluator.evaluate(scenario, result)

    assert outcome.passed is False
    assert "reporter_email" in outcome.reasoning
