"""Day 7: a mock agent that hallucinates a tool call, and the
hallucination-detection mode on ToolCallSequenceEvaluator."""

from harness.evaluators import ToolCallSequenceEvaluator
from harness.mock_agent import AgentResult, CannedAgent, HallucinatesToolCallAgent
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario
from harness.schema import ScenarioSpec

INPUT_TEXT = "Find documentation about the login flow"
CORRECT_SCRIPT = {
    INPUT_TEXT: AgentResult(tool_calls=["search_docs"], output="Found 3 pages."),
}


# --- HallucinatesToolCallAgent -------------------------------------------

def test_hallucinates_agent_appends_the_extra_call():
    agent = HallucinatesToolCallAgent(CORRECT_SCRIPT, hallucinate="delete_ticket")

    result = agent.run(INPUT_TEXT)

    assert result.tool_calls == ["search_docs", "delete_ticket"]
    assert result.output == "Found 3 pages."


def test_underlying_script_is_unmodified():
    agent = HallucinatesToolCallAgent(CORRECT_SCRIPT, hallucinate="delete_ticket")
    agent.run(INPUT_TEXT)

    assert CORRECT_SCRIPT[INPUT_TEXT].tool_calls == ["search_docs"]


# --- ToolCallSequenceEvaluator(mode="hallucination") ---------------------

SCENARIO_WITH_EXPLICIT_ALLOW_LIST = ScenarioSpec(
    id="explicit-allow-list",
    role="search_agent",
    input=INPUT_TEXT,
    expected_tool_calls=["search_docs"],
    allowed_tool_calls=["search_docs", "list_projects"],
)

SCENARIO_WITHOUT_ALLOW_LIST = ScenarioSpec(
    id="implicit-allow-list",
    role="search_agent",
    input=INPUT_TEXT,
    expected_tool_calls=["search_docs"],
    # allowed_tool_calls omitted on purpose — should default to
    # expected_tool_calls.
)


def test_correct_agent_passes_hallucination_check():
    evaluator = ToolCallSequenceEvaluator(mode="hallucination")
    result = AgentResult(tool_calls=["search_docs"])

    assert evaluator.evaluate(SCENARIO_WITHOUT_ALLOW_LIST, result).passed is True


def test_hallucinated_call_fails_the_check():
    evaluator = ToolCallSequenceEvaluator(mode="hallucination")
    result = AgentResult(tool_calls=["search_docs", "delete_ticket"])

    outcome = evaluator.evaluate(SCENARIO_WITHOUT_ALLOW_LIST, result)

    assert outcome.passed is False
    assert "delete_ticket" in outcome.reasoning


def test_allow_list_defaults_to_expected_tool_calls_when_unset():
    evaluator = ToolCallSequenceEvaluator(mode="hallucination")
    # list_projects was never expected and no explicit allow-list widens
    # it, so it counts as hallucinated here even though it's a
    # legitimate tool in other scenarios.
    result = AgentResult(tool_calls=["search_docs", "list_projects"])

    outcome = evaluator.evaluate(SCENARIO_WITHOUT_ALLOW_LIST, result)

    assert outcome.passed is False
    assert "list_projects" in outcome.reasoning


def test_explicit_allow_list_permits_calls_beyond_expected():
    evaluator = ToolCallSequenceEvaluator(mode="hallucination")
    # Same extra call as above, but this scenario explicitly widens its
    # allow-list to include list_projects, so it's no longer hallucinated.
    result = AgentResult(tool_calls=["search_docs", "list_projects"])

    outcome = evaluator.evaluate(SCENARIO_WITH_EXPLICIT_ALLOW_LIST, result)

    assert outcome.passed is True


def test_subset_mode_alone_would_miss_the_hallucinated_call():
    # The reason hallucination mode exists as a separate check: subset
    # mode only verifies the required calls happened, and explicitly
    # tolerates extras — so it would wave through a hallucinated call
    # that hallucination mode correctly flags.
    subset_evaluator = ToolCallSequenceEvaluator(mode="subset")
    hallucination_evaluator = ToolCallSequenceEvaluator(mode="hallucination")
    result = AgentResult(tool_calls=["search_docs", "delete_ticket"])

    assert subset_evaluator.evaluate(SCENARIO_WITHOUT_ALLOW_LIST, result).passed is True
    assert hallucination_evaluator.evaluate(SCENARIO_WITHOUT_ALLOW_LIST, result).passed is False


# --- end to end: real scenario file + hallucinating agent ----------------

def test_real_scenario_with_hallucinating_agent_fails_hallucination_check():
    scenario = load_scenario(SCENARIOS_DIR / "search_docs.yaml")
    agent = HallucinatesToolCallAgent(CORRECT_SCRIPT, hallucinate="delete_ticket")
    evaluator = ToolCallSequenceEvaluator(mode="hallucination")

    result = agent.run(scenario.input)
    outcome = evaluator.evaluate(scenario, result)

    assert outcome.passed is False


def test_real_scenario_with_correct_agent_passes_hallucination_check():
    scenario = load_scenario(SCENARIOS_DIR / "search_docs.yaml")
    agent = CannedAgent(CORRECT_SCRIPT)
    evaluator = ToolCallSequenceEvaluator(mode="hallucination")

    result = agent.run(scenario.input)
    outcome = evaluator.evaluate(scenario, result)

    assert outcome.passed is True
