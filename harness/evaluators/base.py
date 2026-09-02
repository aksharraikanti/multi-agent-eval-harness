"""Shared evaluator result type.

Every evaluator (rule-based or, later, LLM-judge) reports the same shape:
did the scenario pass, and why. Rule-based evaluators fill `reasoning`
with a plain description of what was checked; the LLM-judge (day 16+)
fills it with the judge's own explanation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    reasoning: str
