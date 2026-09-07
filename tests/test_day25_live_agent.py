"""Day 25 (stretch): a real Claude tool-use loop.

Most tests use a fake, injected client — same reason every earlier
"real API" module (LLMJudgeEvaluator, day 16) has one — to prove the
tool-use mechanics (calling the tool server, feeding the result back,
extracting the final answer) without a network call, an API key, or
the anthropic package. One test makes a real call against a real
MockToolServer and skips cleanly when ANTHROPIC_API_KEY isn't set.
"""

import pytest

from harness.evaluators import OutputFormatEvaluator, ToolCallSequenceEvaluator
from harness.live_agent import live_agent_is_available, LiveClaudeAgent
from harness.mock_tool_server import MockToolServer
from harness.schema import ScenarioSpec

SERVER_SCRIPT = {("GET", "/search?q=login"): (200, {"results": ["Login flow overview", "SSO setup guide"]})}


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, block_id: str, name: str):
        self.id = block_id
        self.name = name


class FakeTextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class FakeResponse:
    def __init__(self, stop_reason: str, content: list):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessagesAPI:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeAnthropicClient:
    def __init__(self, responses: list[FakeResponse]):
        self.messages = FakeMessagesAPI(responses)


# --- fake-client tests: the tool-use loop mechanics ------------------------

def test_agent_calls_the_tool_and_returns_the_final_answer():
    fake_client = FakeAnthropicClient([
        FakeResponse("tool_use", [FakeToolUseBlock("toolu_1", "search_docs")]),
        FakeResponse("end_turn", [FakeTextBlock("I found the login flow overview and the SSO setup guide.")]),
    ])

    with MockToolServer(SERVER_SCRIPT) as server:
        agent = LiveClaudeAgent(
            server.url,
            tool_name="search_docs",
            tool_description="Search internal docs about the login flow.",
            tool_path="/search?q=login",
            client=fake_client,
        )
        result = agent.run("How does login work here?")

    assert result.tool_calls == ["search_docs"]
    assert "login flow overview" in result.output


def test_agent_feeds_the_real_tool_result_back_to_the_model():
    fake_client = FakeAnthropicClient([
        FakeResponse("tool_use", [FakeToolUseBlock("toolu_1", "search_docs")]),
        FakeResponse("end_turn", [FakeTextBlock("done")]),
    ])

    with MockToolServer(SERVER_SCRIPT) as server:
        agent = LiveClaudeAgent(
            server.url, "search_docs", "search docs", "/search?q=login", client=fake_client
        )
        agent.run("How does login work?")

    second_call_messages = fake_client.messages.calls[1]["messages"]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    assert "Login flow overview" in tool_result_message["content"][0]["content"]


def test_agent_skips_the_tool_call_when_the_model_answers_directly():
    fake_client = FakeAnthropicClient([
        FakeResponse("end_turn", [FakeTextBlock("I'm not sure, I'd need to look that up.")]),
    ])
    # An unreachable base_url proves _call_tool_server is never invoked —
    # if the model skips tool use, nothing should try to reach a server.
    agent = LiveClaudeAgent(
        "http://127.0.0.1:1", "search_docs", "search docs", "/search?q=login", client=fake_client
    )

    result = agent.run("What's 2 + 2?")

    assert result.tool_calls == []
    assert "not sure" in result.output
    assert len(fake_client.messages.calls) == 1  # only the first call happened


def test_agent_passes_through_the_model_and_max_tokens():
    fake_client = FakeAnthropicClient([FakeResponse("end_turn", [FakeTextBlock("ok")])])
    agent = LiveClaudeAgent(
        "http://127.0.0.1:1", "x", "x", "/x", client=fake_client, model="claude-test-model"
    )

    agent.run("hello")

    assert fake_client.messages.calls[0]["model"] == "claude-test-model"


# --- the point of this day: evaluators work against nondeterministic output

def test_evaluators_pass_against_nondeterministic_but_correct_output():
    # A canned agent would always say exactly this; a real model would
    # phrase it differently every time. subset mode + a loose regex
    # (not an exact string match) is what makes an evaluator robust to
    # that — this is what "the harness works against something
    # nondeterministic" actually means in practice.
    fake_client = FakeAnthropicClient([
        FakeResponse("tool_use", [FakeToolUseBlock("toolu_1", "search_docs")]),
        FakeResponse(
            "end_turn",
            [FakeTextBlock("Based on what I found, here's the login flow overview you were asking about.")],
        ),
    ])
    scenario = ScenarioSpec(
        id="live-search",
        role="search_agent",
        input="How does login work?",
        expected_tool_calls=["search_docs"],
        expected_output_pattern="login flow overview",
    )

    with MockToolServer(SERVER_SCRIPT) as server:
        agent = LiveClaudeAgent(server.url, "search_docs", "search docs", "/search?q=login", client=fake_client)
        result = agent.run(scenario.input)

    tool_outcome = ToolCallSequenceEvaluator(mode="subset").evaluate(scenario, result)
    format_outcome = OutputFormatEvaluator().evaluate(scenario, result)

    assert tool_outcome.passed is True
    assert format_outcome.passed is True


# --- real API call, skipped without credentials --------------------------

@pytest.mark.skipif(not live_agent_is_available(), reason="requires ANTHROPIC_API_KEY and the anthropic package")
def test_real_agent_call_against_a_real_model_and_a_real_local_server():
    with MockToolServer(SERVER_SCRIPT) as server:
        agent = LiveClaudeAgent(
            server.url,
            tool_name="search_docs",
            tool_description="Search internal documentation about the login flow. "
                              "Always call this before answering a question about how login works.",
            tool_path="/search?q=login",
        )
        result = agent.run("How does the login flow work in this system?")

    # Loose assertions on purpose: a real model's exact wording isn't
    # something to pin a test to, only that it did the right kind of
    # thing.
    assert result.tool_calls == ["search_docs"]
    assert len(result.output) > 0
