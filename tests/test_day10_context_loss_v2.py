"""Day 10: context-loss detector v2 — hallucinated handoff-context keys,
opt-in via check_hallucinated_keys."""

from harness.agent_registry import get_agent
from harness.evaluators import ContextLossEvaluator
from harness.mock_agent import AgentResult, HallucinatesContextKeyAgent
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario
from harness.schema import ScenarioSpec

HANDOFF_SCENARIO = ScenarioSpec(
    id="handoff-example",
    role="orchestrator",
    input="hello",
    handoff_to="worker_agent",
    context_passed={"project_key": "DEMO", "title": "Fix login bug"},
)


def test_hallucination_check_is_off_by_default():
    # Same case as day 9's "v1 ignores extra keys" test, restated here to
    # make the default explicit at the point where the opt-in flag exists.
    evaluator = ContextLossEvaluator()
    result = AgentResult(
        handoff_context={"project_key": "DEMO", "title": "Fix login bug", "due_date": "2026-09-05"}
    )

    assert evaluator.evaluate(HANDOFF_SCENARIO, result).passed is True


def test_hallucinated_key_fails_when_enabled():
    evaluator = ContextLossEvaluator(check_hallucinated_keys=True)
    result = AgentResult(
        handoff_context={"project_key": "DEMO", "title": "Fix login bug", "due_date": "2026-09-05"}
    )

    outcome = evaluator.evaluate(HANDOFF_SCENARIO, result)

    assert outcome.passed is False
    assert "due_date" in outcome.reasoning


def test_exact_match_still_passes_when_enabled():
    evaluator = ContextLossEvaluator(check_hallucinated_keys=True)
    result = AgentResult(handoff_context={"project_key": "DEMO", "title": "Fix login bug"})

    assert evaluator.evaluate(HANDOFF_SCENARIO, result).passed is True


def test_missing_and_hallucinated_are_both_reported_together():
    evaluator = ContextLossEvaluator(check_hallucinated_keys=True)
    # title dropped, due_date invented — two distinct problems in one run.
    result = AgentResult(handoff_context={"project_key": "DEMO", "due_date": "2026-09-05"})

    outcome = evaluator.evaluate(HANDOFF_SCENARIO, result)

    assert outcome.passed is False
    assert "title" in outcome.reasoning
    assert "due_date" in outcome.reasoning


# --- HallucinatesContextKeyAgent ------------------------------------------

def test_hallucinates_context_key_agent_adds_the_key():
    script = {
        "hello": AgentResult(
            tool_calls=["parse_request"],
            output="ok",
            handoff_context={"project_key": "DEMO"},
        )
    }
    agent = HallucinatesContextKeyAgent(script, key="due_date", value="2026-09-05")

    result = agent.run("hello")

    assert result.handoff_context == {"project_key": "DEMO", "due_date": "2026-09-05"}
    assert result.tool_calls == ["parse_request"]  # untouched


def test_hallucinates_context_key_agent_creates_context_if_none_existed():
    script = {"hello": AgentResult(tool_calls=["x"], output="ok")}  # no handoff_context at all
    agent = HallucinatesContextKeyAgent(script, key="due_date", value="2026-09-05")

    result = agent.run("hello")

    assert result.handoff_context == {"due_date": "2026-09-05"}


def test_underlying_script_is_unmodified():
    script = {
        "hello": AgentResult(
            tool_calls=["parse_request"],
            output="ok",
            handoff_context={"project_key": "DEMO"},
        )
    }
    agent = HallucinatesContextKeyAgent(script, key="due_date", value="2026-09-05")
    agent.run("hello")

    assert script["hello"].handoff_context == {"project_key": "DEMO"}


# --- end to end: real scenario + real agents -----------------------------

def test_registered_orchestrator_passes_v2_check():
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    agent = get_agent(scenario.role)
    evaluator = ContextLossEvaluator(check_hallucinated_keys=True)

    result = agent.run(scenario.input)

    assert evaluator.evaluate(scenario, result).passed is True


def test_hallucinating_agent_fails_the_real_handoff_scenario_under_v2():
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    good_script = {
        scenario.input: AgentResult(
            tool_calls=["parse_request"],
            output="Handing off to ticket_agent.",
            handoff_context=dict(scenario.context_passed),
        )
    }
    faulty_agent = HallucinatesContextKeyAgent(good_script, key="due_date", value="2026-09-05")
    evaluator = ContextLossEvaluator(check_hallucinated_keys=True)

    result = faulty_agent.run(scenario.input)
    outcome = evaluator.evaluate(scenario, result)

    assert outcome.passed is False
    assert "due_date" in outcome.reasoning


def test_same_hallucinating_agent_passes_under_v1_default():
    # The whole point of the opt-in flag: a hallucinated key is only a
    # failure if the scenario/evaluator combination is actually checking
    # for it.
    scenario = load_scenario(SCENARIOS_DIR / "handoff_create_ticket.yaml")
    good_script = {
        scenario.input: AgentResult(
            tool_calls=["parse_request"],
            output="Handing off to ticket_agent.",
            handoff_context=dict(scenario.context_passed),
        )
    }
    faulty_agent = HallucinatesContextKeyAgent(good_script, key="due_date", value="2026-09-05")
    evaluator = ContextLossEvaluator()  # v1 default

    result = faulty_agent.run(scenario.input)

    assert evaluator.evaluate(scenario, result).passed is True
