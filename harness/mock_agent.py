"""Deterministic mock agents.

Day 1: a single canned agent that always returns the same tool-call
sequence for a given input. No randomness, no timing-dependent branching —
mock agents stay deterministic by construction so the harness's own tests
never flake.
"""

import json
import time
import urllib.request
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentResult:
    tool_calls: list[str] = field(default_factory=list)
    output: str = ""

    # The context an orchestrator actually hands off to a worker agent
    # (day 8+). None for single-agent scenarios. Days 9-10's context-loss
    # detector diffs this observed value against the scenario's
    # context_passed (what should have been handed off).
    handoff_context: dict | None = None

    # Wall-clock time the agent took to produce this result, in
    # milliseconds (day 21+). None for agents that don't do real work
    # worth timing (CannedAgent and its wrappers execute instantly) —
    # only HttpAgent measures this, since it's the only agent making an
    # actual network call. A fabricated number for an instant dict
    # lookup would be more misleading than no number at all.
    latency_ms: float | None = None


class CannedAgent:
    """Returns a fixed, pre-scripted tool-call sequence for one known input.

    This is the simplest possible mock agent: a lookup table from input to
    a canned result. Later agents will simulate specific failure modes
    (dropped calls, hallucinated calls, timeouts); this one exists to prove
    the runner + evaluator pipeline works end to end against a "correct"
    agent first.
    """

    def __init__(self, script: dict[str, AgentResult]):
        self._script = script

    def run(self, input_text: str) -> AgentResult:
        if input_text not in self._script:
            raise KeyError(f"CannedAgent has no scripted response for input: {input_text!r}")
        return self._script[input_text]


class DropsToolCallAgent(CannedAgent):
    """A CannedAgent that deterministically forgets one tool call.

    Wraps a correct script and removes a specific tool call from every
    response it returns — simulating an agent that skips a required step
    in a multi-call sequence (e.g. creating a ticket without first
    verifying the project exists). The underlying script stays correct so
    a test can point at exactly one line — the wrapper — as the cause of
    the failure, rather than a wrong scenario definition.
    """

    def __init__(self, script: dict[str, AgentResult], drop: str):
        super().__init__(script)
        self._drop = drop

    def run(self, input_text: str) -> AgentResult:
        result = super().run(input_text)
        filtered_calls = [c for c in result.tool_calls if c != self._drop]
        return AgentResult(
            tool_calls=filtered_calls,
            output=result.output,
            handoff_context=result.handoff_context,
            latency_ms=result.latency_ms,
        )


class HallucinatesToolCallAgent(CannedAgent):
    """A CannedAgent that deterministically invents one extra tool call.

    Wraps a correct script and appends a tool call that was never part of
    the scripted response — simulating an agent that takes an action it
    was never supposed to (e.g. calling delete_ticket while answering a
    read-only search question). Like DropsToolCallAgent, the underlying
    script stays correct so the wrapper is unambiguously the cause of the
    failure.
    """

    def __init__(self, script: dict[str, AgentResult], hallucinate: str):
        super().__init__(script)
        self._hallucinate = hallucinate

    def run(self, input_text: str) -> AgentResult:
        result = super().run(input_text)
        return AgentResult(
            tool_calls=[*result.tool_calls, self._hallucinate],
            output=result.output,
            handoff_context=result.handoff_context,
            latency_ms=result.latency_ms,
        )


class DropsContextKeyAgent(CannedAgent):
    """A CannedAgent that deterministically drops one key from its
    handoff context.

    Wraps a correct script and removes a specific key from
    handoff_context on every response — simulating an orchestrator that
    silently loses a piece of information on the way to a worker agent
    (e.g. forgetting to pass the reporter's email). The underlying
    script's tool_calls and output are untouched.
    """

    def __init__(self, script: dict[str, AgentResult], drop_key: str):
        super().__init__(script)
        self._drop_key = drop_key

    def run(self, input_text: str) -> AgentResult:
        result = super().run(input_text)
        if result.handoff_context is None:
            return result
        filtered_context = {k: v for k, v in result.handoff_context.items() if k != self._drop_key}
        return AgentResult(
            tool_calls=result.tool_calls,
            output=result.output,
            handoff_context=filtered_context,
            latency_ms=result.latency_ms,
        )


class HallucinatesContextKeyAgent(CannedAgent):
    """A CannedAgent that deterministically invents one extra handoff-
    context key.

    Wraps a correct script and adds a key/value pair to handoff_context
    that was never part of the scripted response — simulating an
    orchestrator that fabricates information rather than losing it (e.g.
    inventing a due_date nobody asked for). tool_calls and output are
    untouched; if the wrapped script has no handoff_context at all, one
    is created containing only the invented key.
    """

    def __init__(self, script: dict[str, AgentResult], key: str, value):
        super().__init__(script)
        self._key = key
        self._value = value

    def run(self, input_text: str) -> AgentResult:
        result = super().run(input_text)
        context = dict(result.handoff_context or {})
        context[self._key] = self._value
        return AgentResult(
            tool_calls=result.tool_calls,
            output=result.output,
            handoff_context=context,
            latency_ms=result.latency_ms,
        )


class AgentTimeoutError(Exception):
    """Raised by a mock agent that times out before producing any result."""


class TimesOutAgent(CannedAgent):
    """A CannedAgent that simulates hitting a timeout.

    With partial_after=None (the default), the agent times out
    completely: run() raises AgentTimeoutError instead of returning
    anything — simulating an agent that never came back at all. The
    runner needs an explicit try/except for this, since it's the only
    mock-agent failure mode so far that doesn't produce an AgentResult
    an evaluator could even look at.

    With partial_after=N, the agent instead returns a result truncated to
    the first N tool calls, empty output, and no handoff context —
    simulating a timeout that cut the agent off mid-execution rather than
    before it started. This needs no special runner handling: a
    truncated tool-call list is just a normal AgentResult that
    ToolCallSequenceEvaluator already knows how to fail.

    Deterministic like every other mock agent here — no real sleeping,
    no randomness. The same input always produces the same (lack of)
    result.
    """

    def __init__(self, script: dict[str, AgentResult], partial_after: int | None = None):
        super().__init__(script)
        self._partial_after = partial_after

    def run(self, input_text: str) -> AgentResult:
        result = super().run(input_text)

        if self._partial_after is None:
            raise AgentTimeoutError(f"agent timed out running input: {input_text!r}")

        return AgentResult(
            tool_calls=result.tool_calls[: self._partial_after],
            output="",
            handoff_context=None,
        )


class HttpAgent:
    """An agent whose response comes from a real HTTP call to a mock
    tool server (day 12), instead of a hardcoded Python dict — the first
    agent in this project that's genuinely "live" in the sense an eval
    harness cares about: a real request goes out over a real socket and
    a real response comes back, even though the server on the other end
    is still fully deterministic and local. Doesn't subclass CannedAgent
    (there's no canned AgentResult to look up) — it only needs to match
    the same run(input_text) -> AgentResult shape every other agent here
    uses.

    script maps input_text -> (tool_call_name, method, path). A
    non-2xx response or a connection failure raises (HTTPError /
    URLError) rather than being caught here — the CLI's existing
    crash-isolation already knows what to do with an exception from
    agent.run(), so there's no reason to invent a second error channel.
    """

    def __init__(self, base_url: str, script: dict[str, tuple[str, str, str]]):
        self._base_url = base_url
        self._script = script

    def run(self, input_text: str) -> AgentResult:
        if input_text not in self._script:
            raise KeyError(f"HttpAgent has no scripted request for input: {input_text!r}")

        tool_call_name, method, path = self._script[input_text]

        request = urllib.request.Request(self._base_url + path, method=method)
        start = time.perf_counter()
        with urllib.request.urlopen(request) as response:
            body = json.loads(response.read())
        latency_ms = (time.perf_counter() - start) * 1000

        return AgentResult(tool_calls=[tool_call_name], output=json.dumps(body), latency_ms=latency_ms)
