"""Day 25 (stretch): swap a mock agent for a real Claude API call.

LiveClaudeAgent wires a real tool-use loop, backed by a real
MockToolServer (day 12) over real HTTP (day 13's pattern) — but instead
of a scripted (tool_call_name, method, path) lookup, an actual Claude
model decides whether to call the tool and what to say. This is the
harness's first genuinely nondeterministic agent: the same input can
plausibly produce different wording, or even a different decision,
across runs. Every mock agent so far has been deterministic by design
(that was the whole point, for reproducible tests) — this is where the
harness proves its evaluators still work when that guarantee is gone.

Scoped to exactly one tool and at most one round of tool use. This
exists to prove the pipeline handles nondeterminism, not to build a
general multi-turn agent framework — that would be its own project.

Behind a flag: live_agent_is_available() gates the one real-call test
(tests/test_day25_live_agent.py), same pattern as the LLM-judge's
anthropic_is_available() (day 16). Never wired into agent_registry.py
or DEFAULT_EVALUATORS — a real API call costs real money and produces a
nondeterministic result, neither of which belongs in "harness run"'s
always-green, no-secrets-needed default suite.
"""

import json
import os
import urllib.request

from harness.mock_agent import AgentResult

LIVE_AGENT_MODEL = "claude-haiku-4-5"


def live_agent_is_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class LiveClaudeAgent:
    """Gives a real Claude model exactly one tool (a GET against a
    MockToolServer) and lets it decide whether to call it and how to
    answer. tool_name/tool_description/tool_path are supplied by the
    caller — this class doesn't hardcode a domain.
    """

    def __init__(
        self,
        base_url: str,
        tool_name: str,
        tool_description: str,
        tool_path: str,
        client=None,
        model: str = LIVE_AGENT_MODEL,
    ):
        self._base_url = base_url
        self._tool_name = tool_name
        self._tool_description = tool_description
        self._tool_path = tool_path
        self._client = client
        self._model = model

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def _call_tool_server(self) -> dict:
        with urllib.request.urlopen(self._base_url + self._tool_path) as response:
            return json.loads(response.read())

    def run(self, input_text: str) -> AgentResult:
        client = self._get_client()
        tools = [{
            "name": self._tool_name,
            "description": self._tool_description,
            "input_schema": {"type": "object", "properties": {}},
        }]
        messages = [{"role": "user", "content": input_text}]
        tool_calls: list[str] = []

        response = client.messages.create(model=self._model, max_tokens=500, tools=tools, messages=messages)

        if response.stop_reason == "tool_use":
            tool_use_block = next(block for block in response.content if block.type == "tool_use")
            tool_calls.append(tool_use_block.name)
            tool_result = self._call_tool_server()

            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use_block.id,
                    "content": json.dumps(tool_result),
                }],
            })

            response = client.messages.create(model=self._model, max_tokens=500, tools=tools, messages=messages)

        output_text = "".join(block.text for block in response.content if block.type == "text")

        return AgentResult(tool_calls=tool_calls, output=output_text)
