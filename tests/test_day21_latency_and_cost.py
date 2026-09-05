"""Day 21: latency (HttpAgent) and judge cost (LLMJudgeEvaluator),
persisted into the SQLite run-log and shown on the dashboard.
"""

from harness.cli import evaluate_scenario, ScenarioOutcome
from harness.dashboard import _query_judge_cost, _query_pass_rate_by_role, generate_dashboard
from harness.evaluators.base import EvaluationResult
from harness.llm_judge import LLMJudgeEvaluator
from harness.mock_agent import AgentResult, DropsToolCallAgent, HttpAgent
from harness.mock_tool_server import MockToolServer
from harness.run_db import connect, write_run
from harness.schema import ScenarioSpec


# --- HttpAgent latency measurement -----------------------------------------

def test_http_agent_records_a_positive_latency():
    server_script = {("GET", "/search?q=login"): (200, {"results": ["ok"]})}
    agent_script = {"find docs": ("search_docs", "GET", "/search?q=login")}

    with MockToolServer(server_script) as server:
        agent = HttpAgent(server.url, agent_script)
        result = agent.run("find docs")

    assert result.latency_ms is not None
    assert result.latency_ms > 0


def test_canned_agent_never_fabricates_a_latency():
    from harness.mock_agent import CannedAgent

    agent = CannedAgent({"hello": AgentResult(tool_calls=["x"])})
    result = agent.run("hello")

    assert result.latency_ms is None


def test_wrapper_agents_preserve_latency_from_the_underlying_result():
    # Regression-style check, same spirit as day 9's handoff_context fix:
    # a wrapper that rebuilds AgentResult must carry latency_ms through.
    script = {"hello": AgentResult(tool_calls=["x", "y"], latency_ms=42.0)}
    agent = DropsToolCallAgent(script, drop="y")

    result = agent.run("hello")

    assert result.latency_ms == 42.0


def test_evaluate_scenario_carries_latency_into_the_outcome():
    server_script = {("GET", "/search?q=login"): (200, {"results": ["ok"]})}
    agent_script = {"find docs": ("search_docs", "GET", "/search?q=login")}
    scenario = ScenarioSpec(id="live", role="search_agent", input="find docs", expected_tool_calls=["search_docs"])

    with MockToolServer(server_script) as server:
        agent = HttpAgent(server.url, agent_script)
        outcome = evaluate_scenario(scenario, agent=agent)

    assert outcome.latency_ms is not None
    assert outcome.latency_ms > 0


# --- LLMJudgeEvaluator cost calculation -------------------------------------

class FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class FakeMessage:
    def __init__(self, text: str, input_tokens: int, output_tokens: int):
        self.content = [FakeTextBlock(text)]
        self.usage = FakeUsage(input_tokens, output_tokens)


class FakeMessagesAPI:
    def __init__(self, message: FakeMessage):
        self._message = message

    def create(self, **kwargs):
        return self._message


class FakeAnthropicClient:
    def __init__(self, message: FakeMessage):
        self.messages = FakeMessagesAPI(message)


RUBRIC_SCENARIO = ScenarioSpec(id="x", role="agent_a", input="hello", success_criteria="must say hi")


def test_judge_computes_cost_from_real_usage_fields():
    # 1000 input tokens @ $1.00/M + 500 output tokens @ $5.00/M
    #   = 0.001 + 0.0025 = 0.0035
    message = FakeMessage("PASS: fine.", input_tokens=1000, output_tokens=500)
    evaluator = LLMJudgeEvaluator(client=FakeAnthropicClient(message))

    outcome = evaluator.evaluate(RUBRIC_SCENARIO, AgentResult(output="hi"))

    assert outcome.cost_usd == 0.0035


def test_judge_cost_is_none_for_trivial_no_rubric_pass():
    no_rubric = ScenarioSpec(id="y", role="agent_a", input="hello")
    evaluator = LLMJudgeEvaluator(client=FakeAnthropicClient(FakeMessage("unused", 0, 0)))

    outcome = evaluator.evaluate(no_rubric, AgentResult(output="anything"))

    assert outcome.cost_usd is None


def test_rule_based_evaluators_leave_cost_as_none():
    from harness.evaluators import OutputFormatEvaluator, ToolCallSequenceEvaluator

    scenario = ScenarioSpec(id="z", role="agent_a", input="hello", expected_tool_calls=["x"])
    result = AgentResult(tool_calls=["x"])

    assert ToolCallSequenceEvaluator().evaluate(scenario, result).cost_usd is None
    assert OutputFormatEvaluator().evaluate(scenario, result).cost_usd is None


# --- persistence: scenarios.latency_ms, evaluator_results.cost_usd -------

def test_write_run_persists_latency_and_cost():
    conn = connect(":memory:")
    outcome = ScenarioOutcome(
        "a",
        passed=True,
        role="search_agent",
        latency_ms=12.5,
        evaluator_results=(("LLMJudgeEvaluator", EvaluationResult(passed=True, reasoning="ok", cost_usd=0.002)),),
    )

    write_run(conn, [outcome])

    latency_row = conn.execute("SELECT latency_ms FROM scenarios").fetchone()
    cost_row = conn.execute("SELECT cost_usd FROM evaluator_results").fetchone()

    assert latency_row == (12.5,)
    assert cost_row == (0.002,)


def test_write_run_persists_none_for_missing_latency_and_cost():
    conn = connect(":memory:")
    outcome = ScenarioOutcome(
        "a",
        passed=True,
        role="project_agent",
        evaluator_results=(("ToolCallSequenceEvaluator", EvaluationResult(passed=True, reasoning="ok")),),
    )

    write_run(conn, [outcome])

    assert conn.execute("SELECT latency_ms FROM scenarios").fetchone() == (None,)
    assert conn.execute("SELECT cost_usd FROM evaluator_results").fetchone() == (None,)


# --- dashboard: avg latency column + total cost line ----------------------

def test_dashboard_shows_average_latency_when_present(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, [
        ScenarioOutcome("a", passed=True, role="search_agent", latency_ms=10.0),
        ScenarioOutcome("b", passed=True, role="search_agent", latency_ms=20.0),
    ])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)
    content = output_path.read_text()

    assert "15 ms" in content  # average of 10.0 and 20.0


def test_dashboard_shows_n_a_when_no_latency_recorded(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, [ScenarioOutcome("a", passed=True, role="project_agent")])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)

    assert "n/a" in output_path.read_text()


def test_dashboard_shows_no_cost_message_when_nothing_recorded(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, [ScenarioOutcome("a", passed=True, role="project_agent")])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)
    content = output_path.read_text()

    assert "No judge cost recorded yet" in content


def test_dashboard_shows_total_cost_when_present(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, [
        ScenarioOutcome(
            "a",
            passed=True,
            role="agent_a",
            evaluator_results=(
                ("LLMJudgeEvaluator", EvaluationResult(passed=True, reasoning="ok", cost_usd=0.0015)),
            ),
        ),
        ScenarioOutcome(
            "b",
            passed=True,
            role="agent_a",
            evaluator_results=(
                ("LLMJudgeEvaluator", EvaluationResult(passed=True, reasoning="ok", cost_usd=0.0025)),
            ),
        ),
    ])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)
    content = output_path.read_text()

    assert "$0.0040" in content
    assert "2 judged call(s)" in content


def test_query_helpers_directly():
    conn = connect(":memory:")
    write_run(conn, [
        ScenarioOutcome(
            "a", passed=True, role="agent_a", latency_ms=100.0,
            evaluator_results=(("J", EvaluationResult(passed=True, reasoning="ok", cost_usd=0.01)),),
        ),
    ])

    rows = _query_pass_rate_by_role(conn)
    total_cost, count = _query_judge_cost(conn)

    assert rows == [("agent_a", 1, 1, 100.0)]
    assert total_cost == 0.01
    assert count == 1
