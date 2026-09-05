"""Reproducibility: log every run's scenario and agent result to JSON,
keyed by run id, so it can be replayed later.

"Replay" means re-running the evaluators against a previously logged
run's AgentResult, without re-invoking the agent or any tool server —
useful for iterating on evaluator logic against a fixed, known trace
instead of re-running (possibly non-deterministic, network-dependent,
or costly) agents every time. replay() takes no agent and touches no
network — that's not a policy this module has to enforce, it's a
consequence of its function signature: there's nothing here that could
invoke one even by accident.
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from harness.evaluators.base import EvaluationResult
from harness.mock_agent import AgentResult
from harness.schema import ScenarioSpec


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    timestamp: str
    scenario: dict
    agent_result: dict


def record_run(scenario: ScenarioSpec, result: AgentResult, run_id: str | None = None) -> RunRecord:
    return RunRecord(
        run_id=run_id or str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        scenario=scenario.model_dump(),
        agent_result=asdict(result),
    )


def write_run_log(record: RunRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(record), indent=2))


def load_run_log(path: Path) -> RunRecord:
    data = json.loads(path.read_text())
    return RunRecord(**data)


def replay(record: RunRecord, evaluators) -> list[EvaluationResult]:
    """Re-run every evaluator against a logged run's scenario and
    result. No agent is invoked and no tool server is contacted — there
    is no agent parameter to this function, so there is nothing here
    that could do either.
    """
    scenario = ScenarioSpec.model_validate(record.scenario)
    result = AgentResult(**record.agent_result)
    return [evaluator.evaluate(scenario, result) for evaluator in evaluators]
