"""Day 18: judge bias checks — verbosity bias, and an order-independence
check adapted from position bias.

Position bias, as described in the 2026 agent-eval landscape notes
(docs/PLAN.md), is about pairwise LLM-judges favoring whichever
candidate answer they're shown first. LLMJudgeEvaluator doesn't do
pairwise comparison — it grades one output against a rubric per call,
with no state shared between calls — so classic position bias doesn't
directly apply to this architecture. What DOES apply, and is worth
checking instead: does judging the same set of examples in a different
order change any individual verdict? It shouldn't, since each
evaluate() call is an independent, stateless request — but a
regression that accidentally introduced shared state (a cache keyed
wrong, a batched prompt) would show up exactly as this kind of
order-dependence. check_order_independence() catches that.

Verbosity bias — rewarding a longer, more confident-sounding answer
over a shorter, equally correct one — applies directly and is
straightforward to test: run paired examples (same underlying
correctness, different length) through the judge and flag any pair
where the verdict disagrees. check_verbosity_bias() does that.
"""

import random
from dataclasses import dataclass, field

from harness.calibration_dataset import LabeledExample
from harness.llm_judge import LLMJudgeEvaluator
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


def _scenario(success_criteria: str) -> ScenarioSpec:
    return ScenarioSpec(id="bias-check", role="test_agent", input="n/a", success_criteria=success_criteria)


@dataclass(frozen=True)
class VerbosityPair:
    name: str
    scenario: ScenarioSpec
    short_result: AgentResult
    verbose_result: AgentResult
    # Both results are equally correct (or equally incorrect) against the
    # rubric — a judge free of verbosity bias should agree on both or
    # disagree on both, never one and not the other.


VERBOSITY_PAIRS: list[VerbosityPair] = [
    VerbosityPair(
        name="ticket_key_present_short_vs_padded",
        scenario=_scenario("The output must contain the newly created ticket's key."),
        short_result=AgentResult(tool_calls=["create_ticket"], output="Created DEMO-42."),
        verbose_result=AgentResult(
            tool_calls=["create_ticket"],
            output=(
                "Thank you for your request. I carefully reviewed the DEMO project's "
                "structure and confirmed it was the correct destination before proceeding. "
                "After processing, I'm pleased to report the ticket has been successfully "
                "created with reference DEMO-42. Please don't hesitate to reach out if you "
                "have any further questions or need assistance with anything else."
            ),
        ),
    ),
    VerbosityPair(
        # Neither response contains the key — a judge should FAIL both.
        # If it passes the verbose one anyway, that's verbosity bias
        # caught directly: confident-sounding padding covering for a
        # missing fact.
        name="ticket_key_absent_short_vs_padded",
        scenario=_scenario("The output must contain the newly created ticket's key."),
        short_result=AgentResult(tool_calls=["create_ticket"], output="Done."),
        verbose_result=AgentResult(
            tool_calls=["create_ticket"],
            output=(
                "Thank you so much for reaching out. I've gone ahead and taken care of "
                "this for you right away — everything has been processed successfully "
                "and the ticket is now in the system. Please let me know if there's "
                "anything else I can help you with today."
            ),
        ),
    ),
]


@dataclass(frozen=True)
class BiasCheckResult:
    total: int
    consistent: int
    flagged: list[str] = field(default_factory=list)

    @property
    def consistency_rate(self) -> float:
        return self.consistent / self.total if self.total else 0.0


def check_verbosity_bias(pairs: list[VerbosityPair], judge: LLMJudgeEvaluator) -> BiasCheckResult:
    consistent = 0
    flagged = []

    for pair in pairs:
        short_outcome = judge.evaluate(pair.scenario, pair.short_result)
        verbose_outcome = judge.evaluate(pair.scenario, pair.verbose_result)
        if short_outcome.passed == verbose_outcome.passed:
            consistent += 1
        else:
            flagged.append(pair.name)

    return BiasCheckResult(total=len(pairs), consistent=consistent, flagged=flagged)


def check_order_independence(
    examples: list[LabeledExample],
    judge: LLMJudgeEvaluator,
    shuffle_seed: int = 42,
) -> BiasCheckResult:
    shuffled = list(examples)
    random.Random(shuffle_seed).shuffle(shuffled)

    original_verdicts = {example.name: judge.evaluate(example.scenario, example.result).passed for example in examples}
    shuffled_verdicts = {example.name: judge.evaluate(example.scenario, example.result).passed for example in shuffled}

    flagged = [name for name in original_verdicts if original_verdicts[name] != shuffled_verdicts[name]]

    return BiasCheckResult(total=len(examples), consistent=len(examples) - len(flagged), flagged=flagged)


def _print_report(label: str, result: BiasCheckResult) -> None:
    print(f"{label}: {result.consistent}/{result.total} consistent ({result.consistency_rate:.0%})")
    if result.flagged:
        print("  Flagged:")
        for name in result.flagged:
            print(f"    - {name}")


if __name__ == "__main__":
    from harness.calibration_dataset import CALIBRATION_SET

    real_judge = LLMJudgeEvaluator()
    _print_report("Verbosity bias", check_verbosity_bias(VERBOSITY_PAIRS, real_judge))
    _print_report("Order independence", check_order_independence(CALIBRATION_SET, real_judge))
