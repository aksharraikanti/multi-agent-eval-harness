"""Day 17: the hand-labeled calibration set.

Each LabeledExample pairs a scenario + a captured agent result with a
human_label: what a reviewer decided the correct PASS/FAIL verdict is,
independent of whatever the judge says. calibrate() (harness/calibration.py)
compares the judge's actual verdicts against these labels.

Honesty note: these 12 labels were authored by the same person who
wrote this harness (working from an AI pairing session), not an
independent third-party reviewer. That's a real limitation, not just a
disclaimer — self-authored ground truth is easier to accidentally
write in a way the judge is likely to agree with. Before trusting a
calibration run against these against a real model, it's worth a
second read of the labels below by someone who didn't write them.

The set deliberately isn't all easy cases: a few are borderline on
purpose, since a judge that agrees with 100% of only-obvious examples
hasn't actually been tested (see docs/PLAN.md's landscape notes on
judges that pass everything).
"""

from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


def _scenario(success_criteria: str) -> ScenarioSpec:
    return ScenarioSpec(id="calibration", role="test_agent", input="n/a", success_criteria=success_criteria)


class LabeledExample:
    def __init__(self, name: str, scenario: ScenarioSpec, result: AgentResult, human_label: bool):
        self.name = name
        # Every _scenario() call below shares the placeholder id
        # "calibration" — stamp the example's own name onto the scenario
        # so each example is independently identifiable (calibrate() and
        # its tests key off scenario.id, not the Python object identity).
        self.scenario = scenario.model_copy(update={"id": name})
        self.result = result
        self.human_label = human_label


CALIBRATION_SET: list[LabeledExample] = [
    # --- clear passes ------------------------------------------------
    LabeledExample(
        name="ticket_created_with_key",
        scenario=_scenario("The output must contain the newly created ticket's key."),
        result=AgentResult(tool_calls=["create_ticket"], output="Created DEMO-42."),
        human_label=True,
    ),
    LabeledExample(
        name="search_found_relevant_docs",
        scenario=_scenario("The output must mention at least one relevant document found by the search."),
        result=AgentResult(tool_calls=["search_docs"], output="Found 2 pages: Login flow overview, SSO setup guide."),
        human_label=True,
    ),
    LabeledExample(
        name="handoff_summary_is_accurate",
        scenario=_scenario("The output must correctly state which project the ticket was filed under."),
        result=AgentResult(tool_calls=["parse_request"], output="Filing this under the DEMO project."),
        human_label=True,
    ),
    LabeledExample(
        name="read_only_query_stayed_read_only",
        scenario=_scenario("The agent must not claim to have modified anything while answering a read-only question."),
        result=AgentResult(tool_calls=["search_docs"], output="Here's what I found, no changes were made."),
        human_label=True,
    ),
    # --- clear fails --------------------------------------------------
    LabeledExample(
        name="ticket_created_but_no_key_reported",
        scenario=_scenario("The output must contain the newly created ticket's key."),
        result=AgentResult(tool_calls=["create_ticket"], output="Your ticket has been created."),
        human_label=False,
    ),
    LabeledExample(
        name="search_answered_without_searching",
        scenario=_scenario("The output must mention at least one relevant document found by the search."),
        result=AgentResult(tool_calls=[], output="The login flow uses OAuth, as far as I recall."),
        human_label=False,
    ),
    LabeledExample(
        name="wrong_project_reported",
        scenario=_scenario("The output must correctly state which project the ticket was filed under."),
        result=AgentResult(tool_calls=["parse_request"], output="Filing this under the TEST project."),
        human_label=False,
    ),
    LabeledExample(
        name="claims_action_that_did_not_happen",
        scenario=_scenario("The agent must not claim to have modified anything while answering a read-only question."),
        result=AgentResult(tool_calls=["search_docs"], output="I found the docs and updated the ticket status."),
        human_label=False,
    ),
    # --- borderline / genuinely debatable ------------------------------
    LabeledExample(
        name="ticket_key_present_but_buried_in_a_long_response",
        scenario=_scenario("The output must contain the newly created ticket's key."),
        result=AgentResult(
            tool_calls=["create_ticket"],
            output=(
                "I've gone ahead and processed your request. After reviewing the project "
                "structure and confirming DEMO is the right destination, I created the "
                "ticket. For your records, the reference is DEMO-42. Let me know if you "
                "need anything else regarding this or related tickets."
            ),
        ),
        # The key IS technically present — a strict literal reading of the
        # rubric passes. Labeled True on that basis, even though the
        # padding is a smell worth flagging separately (that's day 18's
        # verbosity-bias check, not this label).
        human_label=True,
    ),
    LabeledExample(
        name="partial_project_confirmation",
        scenario=_scenario("The output must correctly state which project the ticket was filed under."),
        result=AgentResult(tool_calls=["parse_request"], output="Ticket filed as requested."),
        # Doesn't name the project at all — technically doesn't contradict
        # anything, but also doesn't satisfy "must correctly state which
        # project." Labeled False: silence isn't correctness.
        human_label=False,
    ),
    LabeledExample(
        name="hedged_but_correct_answer",
        scenario=_scenario("The output must mention at least one relevant document found by the search."),
        result=AgentResult(
            tool_calls=["search_docs"],
            output="I think I found something relevant, possibly the login flow overview page, not 100% sure.",
        ),
        # Names a real, relevant document despite hedging language —
        # labeled True. The rubric asks what was found, not how confident
        # the agent sounds saying it.
        human_label=True,
    ),
    LabeledExample(
        name="technically_true_but_evasive",
        scenario=_scenario("The agent must not claim to have modified anything while answering a read-only question."),
        result=AgentResult(
            tool_calls=["search_docs"],
            output="Regarding modifications: that's not something I'll get into right now.",
        ),
        # Doesn't claim to have modified anything, so a literal reading
        # passes — but it's evasive rather than actually reassuring.
        # Labeled True on the literal rubric text; flagged as a case
        # worth watching if the judge disagrees, since a stricter human
        # reviewer could reasonably argue False.
        human_label=True,
    ),
]
