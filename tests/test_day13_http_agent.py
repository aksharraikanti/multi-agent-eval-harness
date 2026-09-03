"""Day 13: wire a mock agent to the mock tool server — the first agent
whose result comes from a real HTTP round-trip instead of a dict
lookup.
"""

import urllib.error

import pytest

from harness.cli import evaluate_scenario
from harness.evaluators import OutputFormatEvaluator, ToolCallSequenceEvaluator
from harness.mock_agent import HttpAgent
from harness.mock_tool_server import MockToolServer
from harness.schema import ScenarioSpec

SERVER_SCRIPT = {
    ("GET", "/search?q=login"): (200, {"results": ["Login flow overview", "SSO setup guide"]}),
}

AGENT_SCRIPT = {
    "Find documentation about the login flow": ("search_docs", "GET", "/search?q=login"),
}

SCENARIO = ScenarioSpec(
    id="http_search_docs",
    role="search_agent",
    input="Find documentation about the login flow",
    expected_tool_calls=["search_docs"],
    expected_output_pattern="Login flow overview",
)


def test_http_agent_returns_a_result_built_from_a_real_response():
    with MockToolServer(SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, AGENT_SCRIPT)
        result = agent.run(SCENARIO.input)

    assert result.tool_calls == ["search_docs"]
    assert "Login flow overview" in result.output
    assert "SSO setup guide" in result.output


def test_unscripted_input_raises_key_error_like_canned_agent():
    with MockToolServer(SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, AGENT_SCRIPT)

        with pytest.raises(KeyError):
            agent.run("nobody scripted this")


def test_non_2xx_server_response_propagates_as_an_exception():
    # The agent's script points at a path the server never scripted, so
    # the server 404s — the agent doesn't swallow that, it propagates,
    # the same way a bad role or a missing script entry does elsewhere.
    unscripted_agent_script = {
        "hello": ("search_docs", "GET", "/nonexistent"),
    }
    with MockToolServer(SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, unscripted_agent_script)

        with pytest.raises(urllib.error.HTTPError):
            agent.run("hello")


def test_server_down_propagates_as_a_connection_error():
    server = MockToolServer(SERVER_SCRIPT)
    server.start()
    url = server.url
    server.stop()

    agent = HttpAgent(url, AGENT_SCRIPT)

    with pytest.raises(urllib.error.URLError):
        agent.run(SCENARIO.input)


# --- the whole pipeline, live: agent -> real HTTP -> evaluators ----------

def test_full_pipeline_against_a_live_http_agent():
    with MockToolServer(SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, AGENT_SCRIPT)
        result = agent.run(SCENARIO.input)

        tool_call_outcome = ToolCallSequenceEvaluator(mode="exact").evaluate(SCENARIO, result)
        output_outcome = OutputFormatEvaluator().evaluate(SCENARIO, result)

    assert tool_call_outcome.passed is True
    assert output_outcome.passed is True


def test_evaluate_scenario_against_a_live_http_agent():
    # Ties together day 11's agent= override (so this doesn't need to be
    # in the "always passes" registry) with day 12's server and today's
    # HttpAgent — the real evaluate_scenario() codepath, not a hand-rolled
    # substitute, run against something that made an actual HTTP call.
    with MockToolServer(SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, AGENT_SCRIPT)
        outcome = evaluate_scenario(SCENARIO, agent=agent)

    assert outcome.passed is True, outcome.failures


def test_evaluate_scenario_reports_a_dead_server_as_a_crash_not_a_hang():
    server = MockToolServer(SERVER_SCRIPT)
    server.start()
    url = server.url
    server.stop()

    agent = HttpAgent(url, AGENT_SCRIPT)
    outcome = evaluate_scenario(SCENARIO, agent=agent)

    assert outcome.passed is False
    assert outcome.crashed is True
    assert outcome.timed_out is False
