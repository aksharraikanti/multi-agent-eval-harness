"""Rule-based evaluator: does the agent's output look like it should?

Two independent, opt-in checks:
- expected_output_pattern: a regex the free-text output must match.
- expected_output_schema: the output is expected to be a JSON object,
  and must contain these top-level keys with these Python types.

A scenario that sets neither field trivially passes — this evaluator
never blocks a scenario that doesn't care about output shape.
"""

import json
import re

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "str": str,
    "int": int,
    "float": (int, float),
    "bool": bool,
    "list": list,
    "dict": dict,
}


class OutputFormatEvaluator:
    def evaluate(self, scenario: ScenarioSpec, result: AgentResult) -> EvaluationResult:
        if scenario.expected_output_pattern is not None:
            pattern_check = self._check_pattern(scenario.expected_output_pattern, result.output)
            if not pattern_check.passed:
                return pattern_check

        if scenario.expected_output_schema is not None:
            schema_check = self._check_schema(scenario.expected_output_schema, result.output)
            if not schema_check.passed:
                return schema_check

        return EvaluationResult(passed=True, reasoning="output format checks satisfied")

    def _check_pattern(self, pattern: str, output: str) -> EvaluationResult:
        if re.search(pattern, output) is None:
            return EvaluationResult(
                passed=False,
                reasoning=f"output {output!r} does not match expected pattern {pattern!r}",
            )
        return EvaluationResult(passed=True, reasoning=f"output matches pattern {pattern!r}")

    def _check_schema(self, expected_schema: dict[str, str], output: str) -> EvaluationResult:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as e:
            return EvaluationResult(passed=False, reasoning=f"output is not valid JSON: {e}")

        if not isinstance(parsed, dict):
            return EvaluationResult(
                passed=False,
                reasoning=f"expected a JSON object, got {type(parsed).__name__}",
            )

        for key, type_name in expected_schema.items():
            if key not in parsed:
                return EvaluationResult(passed=False, reasoning=f"output JSON missing required key {key!r}")

            expected_type = _TYPE_MAP.get(type_name)
            if expected_type is None:
                return EvaluationResult(passed=False, reasoning=f"unknown schema type {type_name!r} for key {key!r}")

            value = parsed[key]
            # bool is a subclass of int in Python, so isinstance(True, int)
            # is True. A schema asking for "int" almost certainly doesn't
            # mean "or a boolean" — reject that combination explicitly.
            if type_name == "int" and isinstance(value, bool):
                return EvaluationResult(
                    passed=False,
                    reasoning=f"key {key!r} expected type 'int', got 'bool'",
                )

            if not isinstance(value, expected_type):
                return EvaluationResult(
                    passed=False,
                    reasoning=(
                        f"key {key!r} expected type {type_name!r}, "
                        f"got {type(parsed[key]).__name__}"
                    ),
                )

        return EvaluationResult(passed=True, reasoning="output JSON matches expected schema")
