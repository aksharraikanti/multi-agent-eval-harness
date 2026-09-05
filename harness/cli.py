"""Day 6: the real runner CLI. Day 11 adds explicit timeout handling.

`harness run [paths...]` loads scenarios from one or more directories
and/or files (defaulting to the scenarios/ directory), runs each one
against its registered mock agent, applies every evaluator, and prints
a report. Each scenario runs in its own try/except so one crashing
scenario — an unregistered role, an agent with no scripted response for
the given input, a bug in an evaluator — can't take down the whole
suite run. It reports as a FAIL with the exception, not an aborted run.

A timeout (AgentTimeoutError) gets its own outcome flag and report
status rather than falling into the generic crash bucket: a timeout is
an expected, meaningful outcome an eval harness needs to surface
clearly, not a bug in the harness itself.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

from harness.agent_registry import get_agent
from harness.evaluators import ContextLossEvaluator, OutputFormatEvaluator, ToolCallSequenceEvaluator
from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentTimeoutError
from harness.runner import SCENARIOS_DIR
from harness.scenario_loader import load_scenario, load_scenarios
from harness.schema import ScenarioSpec

DEFAULT_EVALUATORS = (
    ToolCallSequenceEvaluator(mode="exact"),
    OutputFormatEvaluator(),
    ContextLossEvaluator(check_hallucinated_keys=True),
)


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario_id: str
    passed: bool
    failures: tuple[str, ...] = ()
    crashed: bool = False
    timed_out: bool = False
    # One (evaluator class name, EvaluationResult) pair per evaluator that
    # actually ran — empty on a crash or timeout, since no evaluator got
    # the chance to run. Day 19's evaluator_results table is this field,
    # persisted; day 6-18 didn't need this level of detail, only whether
    # the scenario as a whole passed.
    evaluator_results: tuple[tuple[str, EvaluationResult], ...] = ()


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


def evaluate_scenario(scenario: ScenarioSpec, evaluators=DEFAULT_EVALUATORS, agent=None) -> ScenarioOutcome:
    """Run one scenario against its registered agent and every evaluator.

    `agent` defaults to a registry lookup by scenario.role; pass one
    explicitly to evaluate a scenario against a specific agent instance
    (a failure-mode wrapper in a test, for example) without needing it
    registered — the registry is reserved for agents that are supposed
    to pass (see agent_registry.py's docstring).

    A timeout is caught and reported distinctly (see module docstring).
    Any other exception along the way (unknown role, agent with no
    scripted response, an evaluator bug) is caught and reported as a
    crashed outcome, rather than propagating up and killing the whole
    suite run.
    """
    try:
        if agent is None:
            agent = get_agent(scenario.role)
        result = agent.run(scenario.input)

        failures = []
        evaluator_results = []
        for evaluator in evaluators:
            outcome = evaluator.evaluate(scenario, result)
            evaluator_results.append((type(evaluator).__name__, outcome))
            if not outcome.passed:
                failures.append(outcome.reasoning)

        return ScenarioOutcome(
            scenario.id,
            passed=not failures,
            failures=tuple(failures),
            evaluator_results=tuple(evaluator_results),
        )
    except AgentTimeoutError as e:
        return ScenarioOutcome(
            scenario.id,
            passed=False,
            failures=(str(e),),
            timed_out=True,
        )
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
        if outcome.timed_out:
            status = "TIMEOUT"
        elif outcome.passed:
            status = "PASS"
        else:
            status = "FAIL"
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
