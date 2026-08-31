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
