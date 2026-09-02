"""The 'correct' mock agent for each scenario role.

This is the source of truth for what passing behavior looks like when
the CLI (day 6) runs the full scenario suite — every registered agent
here is scripted to do the right thing. Agents that simulate a specific
failure mode (DropsToolCallAgent and friends) live in tests, not here:
this registry exists to demonstrate the harness against agents that are
supposed to pass, not to catalog every failure mode.
"""

from harness.mock_agent import AgentResult, CannedAgent

DEFAULT_AGENTS: dict[str, CannedAgent] = {
    "project_agent": CannedAgent({
        "What projects do I have access to?": AgentResult(
            tool_calls=["list_projects"],
            output="You have access to 2 projects: DEMO, TEST",
        ),
    }),
    "ticket_agent": CannedAgent({
        "Create a ticket in the DEMO project titled 'Fix login bug'": AgentResult(
            tool_calls=["list_projects", "create_ticket"],
            output="Created DEMO-42.",
        ),
    }),
}


def get_agent(role: str) -> CannedAgent:
    try:
        return DEFAULT_AGENTS[role]
    except KeyError:
        raise KeyError(f"no mock agent registered for role {role!r}") from None
