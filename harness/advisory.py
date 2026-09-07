"""Day 23: regression gate policy.

Rule-based evaluators (harness/cli.py's DEFAULT_EVALUATORS) are
CI-blocking. The LLM-judge is advisory-only, permanently — even after
day 17's calibration. Calibration makes the judge trustworthy to READ,
not safe to GATE ON: the whole point of a hand-labeled agreement rate
is to know how often the judge is *right*, and "usually right" is a
fine basis for a human to read an opinion, and a bad basis for an
automated build to fail on.

This module is where that opinion actually gets read. run_advisory_judge()
runs LLMJudgeEvaluator across a scenario suite (reusing evaluate_scenario's
crash isolation) and reports PASS/FAIL per scenario — but advisory_main()
always returns 0, no matter what the judge says. There is no path from
a judge verdict to a process exit code anywhere in this module. That's
not a convention someone has to remember to follow; it's the only thing
this file's main() can do.
"""

import sys
from pathlib import Path

from harness.cli import collect_scenarios, evaluate_scenario, ScenarioOutcome
from harness.llm_judge import LLMJudgeEvaluator
from harness.runner import SCENARIOS_DIR


def run_advisory_judge(paths: list[Path], judge: LLMJudgeEvaluator | None = None) -> list[ScenarioOutcome]:
    judge = judge if judge is not None else LLMJudgeEvaluator()
    scenarios = collect_scenarios(paths)
    return [evaluate_scenario(scenario, evaluators=(judge,)) for scenario in scenarios]


def print_advisory_report(outcomes: list[ScenarioOutcome]) -> None:
    print("ADVISORY — LLM-judge opinions (non-blocking, never affects CI or exit code):")
    for outcome in outcomes:
        status = "JUDGE PASS" if outcome.passed else "JUDGE FAIL"
        print(f"[{status}] {outcome.scenario_id}")
        for failure in outcome.failures:
            print(f"    {failure}")


def advisory_main(argv: list[str] | None = None, judge: LLMJudgeEvaluator | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    paths = [Path(p) for p in argv] or [SCENARIOS_DIR]

    outcomes = run_advisory_judge(paths, judge=judge)
    print_advisory_report(outcomes)

    return 0  # always — see module docstring. Nothing here reads outcomes.


if __name__ == "__main__":
    sys.exit(advisory_main())
