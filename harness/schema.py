"""Scenario spec schema v1.

A scenario describes one thing to ask one agent, and what "correct" looks
like. `role` names which agent the scenario targets (mock agents are
looked up by this name). `expected_tool_calls` backs the day-1 style
exact/subset tool-call check; `success_criteria` is free text for now —
it becomes the LLM-judge's rubric input once that lands (day 16-18).

Fields added for multi-agent handoff scenarios (day 8 onward) are
optional so scenarios written against this same schema version never
need a migration.
"""

from pydantic import BaseModel, Field


class ScenarioSpec(BaseModel):
    id: str
    role: str
    input: str
    expected_tool_calls: list[str] = Field(default_factory=list)
    success_criteria: str | None = None

    # The full set of tool calls this scenario permits (day 7+). Optional:
    # when omitted, the allow-list defaults to expected_tool_calls, so an
    # existing scenario that never mentions this field still implicitly
    # forbids any call it didn't ask for. Set it explicitly to widen the
    # allow-list beyond what's strictly expected.
    allowed_tool_calls: list[str] | None = None

    # Output-format fields (day 5+). Both optional and independent: a
    # scenario can check a free-text pattern, a JSON shape, both, or
    # neither (in which case OutputFormatEvaluator trivially passes).
    expected_output_pattern: str | None = None
    expected_output_schema: dict[str, str] | None = None

    # Multi-agent handoff fields (day 8+). Optional: a single-agent
    # scenario simply omits them.
    handoff_to: str | None = None
    context_passed: dict | None = None
