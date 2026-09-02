"""Day 6: the real runner CLI.

`harness run [paths...]` loads scenarios from one or more directories
and/or files (defaulting to the scenarios/ directory), runs each one
against its registered mock agent, applies every evaluator, and prints
a report. Each scenario runs in its own try/except so one crashing
scenario — an unregistered role, an agent with no scripted response for
the given input, a bug in an evaluator — can't take down the whole
suite run. It reports as a FAIL with the exception, not an aborted run.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from harness.agent_registry import get_agent
from harness.evaluators import OutputFormatEvaluator, ToolCallSequenceEvaluator
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario, load_scenarios
from harness.schema import ScenarioSpec

DEFAULT_EVALUATORS = (ToolCallSequenceEvaluator(mode="exact"), OutputFormatEvaluator())


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario_id: str
    passed: bool
    failures: tuple[str, ...] = ()
    crashed: bool = False


def collect_scenarios(paths: list[Path]) -> list[ScenarioSpec]:
    """Expand a mix of directories and individual scenario files into a
    flat list of scenarios. A directory contributes every *.yaml file in
    it; a file is loaded directly.
    """
    scenarios: list[ScenarioSpec] = []
    for path in paths:
        if path.is_dir():
            scenarios.extend(load_scenarios(path))
        else:
            scenarios.append(load_scenario(path))
    return scenarios


def evaluate_scenario(scenario: ScenarioSpec, evaluators=DEFAULT_EVALUATORS) -> ScenarioOutcome:
    """Run one scenario against its registered agent and every evaluator.

    Any exception along the way (unknown role, agent with no scripted
    response, an evaluator bug) is caught here and reported as a crashed
    outcome, rather than propagating up and killing the whole suite run.
    """
    try:
        agent = get_agent(scenario.role)
        result = agent.run(scenario.input)

        failures = []
        for evaluator in evaluators:
            outcome = evaluator.evaluate(scenario, result)
            if not outcome.passed:
                failures.append(outcome.reasoning)

        return ScenarioOutcome(scenario.id, passed=not failures, failures=tuple(failures))
    except Exception as e:
        return ScenarioOutcome(
            scenario.id,
            passed=False,
            failures=(f"scenario crashed: {e!r}",),
            crashed=True,
        )


def run_suite(paths: list[Path], evaluators=DEFAULT_EVALUATORS) -> list[ScenarioOutcome]:
    return [evaluate_scenario(scenario, evaluators) for scenario in collect_scenarios(paths)]


def print_report(outcomes: list[ScenarioOutcome]) -> None:
    for outcome in outcomes:
        status = "PASS" if outcome.passed else "FAIL"
        print(f"[{status}] {outcome.scenario_id}")
        for failure in outcome.failures:
            print(f"    {failure}")

    passed = sum(1 for o in outcomes if o.passed)
    total = len(outcomes)
    print(f"\n{passed}/{total} scenarios passed")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv or argv[0] != "run":
        print("usage: harness run [paths...]", file=sys.stderr)
        return 2

    raw_paths = argv[1:] or [str(SCENARIOS_DIR)]
    paths = [Path(p) for p in raw_paths]

    outcomes = run_suite(paths)
    print_report(outcomes)

    return 0 if all(outcome.passed for outcome in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
