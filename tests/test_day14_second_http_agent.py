"""Day 14: a second mock tool server + a second HttpAgent, using neither
class from day 12/13 differently — the point is proving MockToolServer
and HttpAgent generalize to a completely different fake API without any
code changes, and that two independent server+agent pairs can run at
the same time without interfering with each other.
"""

from harness.cli import evaluate_scenario
from harness.evaluators import OutputFormatEvaluator, ToolCallSequenceEvaluator
from harness.mock_agent import HttpAgent
from harness.mock_tool_server import MockToolServer
from harness.schema import ScenarioSpec

# --- server/agent pair #1: search (reused from day 13, for the
# side-by-side test below) --------------------------------------------

SEARCH_SERVER_SCRIPT = {
    ("GET", "/search?q=login"): (200, {"results": ["Login flow overview", "SSO setup guide"]}),
}
SEARCH_AGENT_SCRIPT = {
    "Find documentation about the login flow": ("search_docs", "GET", "/search?q=login"),
}
SEARCH_SCENARIO = ScenarioSpec(
    id="http_search_docs",
    role="search_agent",
    input="Find documentation about the login flow",
    expected_tool_calls=["search_docs"],
    expected_output_pattern="Login flow overview",
)

# --- server/agent pair #2: a completely different fake API — tickets ----

TICKET_SERVER_SCRIPT = {
    ("GET", "/tickets/DEMO-42"): (200, {"id": "DEMO-42", "status": "open", "title": "Fix login bug"}),
}
TICKET_AGENT_SCRIPT = {
    "What's the status of ticket DEMO-42?": ("get_ticket", "GET", "/tickets/DEMO-42"),
}
TICKET_SCENARIO = ScenarioSpec(
    id="http_get_ticket_status",
    role="live_ticket_agent",
    input="What's the status of ticket DEMO-42?",
    expected_tool_calls=["get_ticket"],
    expected_output_pattern='"status": "open"',
)


def test_second_server_and_agent_work_with_zero_new_code():
    with MockToolServer(TICKET_SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, TICKET_AGENT_SCRIPT)
        result = agent.run(TICKET_SCENARIO.input)

    assert result.tool_calls == ["get_ticket"]
    assert '"status": "open"' in result.output
    assert '"id": "DEMO-42"' in result.output


def test_second_pair_passes_the_full_evaluator_pipeline():
    with MockToolServer(TICKET_SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, TICKET_AGENT_SCRIPT)
        result = agent.run(TICKET_SCENARIO.input)

        tool_call_outcome = ToolCallSequenceEvaluator(mode="exact").evaluate(TICKET_SCENARIO, result)
        output_outcome = OutputFormatEvaluator().evaluate(TICKET_SCENARIO, result)

    assert tool_call_outcome.passed is True
    assert output_outcome.passed is True


def test_second_pair_passes_through_evaluate_scenario():
    with MockToolServer(TICKET_SERVER_SCRIPT) as server:
        agent = HttpAgent(server.url, TICKET_AGENT_SCRIPT)
        outcome = evaluate_scenario(TICKET_SCENARIO, agent=agent)

    assert outcome.passed is True, outcome.failures


# --- both pairs at once: prove independence, not just repetition --------

def test_two_independent_server_agent_pairs_run_at_the_same_time():
    # Two servers, each on its own OS-assigned port, each backing a
    # different agent, each answering a different scenario — nothing
    # shared between them but the HttpAgent/MockToolServer classes.
    with MockToolServer(SEARCH_SERVER_SCRIPT) as search_server, \
            MockToolServer(TICKET_SERVER_SCRIPT) as ticket_server:

        assert search_server.url != ticket_server.url

        search_agent = HttpAgent(search_server.url, SEARCH_AGENT_SCRIPT)
        ticket_agent = HttpAgent(ticket_server.url, TICKET_AGENT_SCRIPT)

        search_outcome = evaluate_scenario(SEARCH_SCENARIO, agent=search_agent)
        ticket_outcome = evaluate_scenario(TICKET_SCENARIO, agent=ticket_agent)

    assert search_outcome.passed is True, search_outcome.failures
    assert ticket_outcome.passed is True, ticket_outcome.failures


def test_pointing_the_wrong_agent_at_the_wrong_server_fails_cleanly():
    # search_agent's script asks for /search?q=login, which the ticket
    # server never scripted — should 404 and crash cleanly, not silently
    # succeed against the wrong API.
    with MockToolServer(TICKET_SERVER_SCRIPT) as ticket_server:
        misconfigured_agent = HttpAgent(ticket_server.url, SEARCH_AGENT_SCRIPT)
        outcome = evaluate_scenario(SEARCH_SCENARIO, agent=misconfigured_agent)

    assert outcome.passed is False
    assert outcome.crashed is True
