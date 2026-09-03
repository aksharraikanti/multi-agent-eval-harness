"""Deterministic mock agents.

Day 1: a single canned agent that always returns the same tool-call
sequence for a given input. No randomness, no timing-dependent branching —
mock agents stay deterministic by construction so the harness's own tests
never flake.
"""

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
        )
