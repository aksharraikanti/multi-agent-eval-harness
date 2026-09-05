"""Day 19: SQLite run-log schema.

Where run_log.py (day 15) captures ONE scenario's run for replay, this
module captures a WHOLE SUITE run's history for later querying — pass
rates over time, which scenarios flake, per-evaluator breakdowns. The
dashboard (days 20-21) reads from here.

Three tables:
- runs: one row per `harness run` invocation.
- scenarios: one row per scenario OUTCOME within a run — not a static
  scenario definition (ScenarioSpec already owns that); this is "how did
  this scenario do, in this particular run."
- evaluator_results: one row per individual evaluator's verdict for one
  scenario outcome, so a failure traces back to exactly which evaluator
  said what, instead of just an aggregated failure string.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from harness.cli import ScenarioOutcome

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    scenario_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    crashed INTEGER NOT NULL,
    timed_out INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluator_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_row_id INTEGER NOT NULL REFERENCES scenarios(id),
    evaluator_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    reasoning TEXT NOT NULL
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating if necessary) a run-log database and ensure the
    schema exists. Safe to call repeatedly against the same file — every
    statement is CREATE TABLE IF NOT EXISTS.
    """
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def write_run(conn: sqlite3.Connection, outcomes: list[ScenarioOutcome], run_id: str | None = None) -> str:
    """Persist a whole suite run (one runs row, one scenarios row per
    outcome, one evaluator_results row per evaluator that actually ran)
    and return the run_id used.
    """
    run_id = run_id or str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    total = len(outcomes)
    passed = sum(1 for outcome in outcomes if outcome.passed)

    conn.execute(
        "INSERT INTO runs (run_id, timestamp, total, passed) VALUES (?, ?, ?, ?)",
        (run_id, timestamp, total, passed),
    )

    for outcome in outcomes:
        cursor = conn.execute(
            "INSERT INTO scenarios (run_id, scenario_id, passed, crashed, timed_out) VALUES (?, ?, ?, ?, ?)",
            (run_id, outcome.scenario_id, int(outcome.passed), int(outcome.crashed), int(outcome.timed_out)),
        )
        scenario_row_id = cursor.lastrowid

        for evaluator_name, evaluation in outcome.evaluator_results:
            conn.execute(
                """INSERT INTO evaluator_results
                   (scenario_row_id, evaluator_name, passed, reasoning)
                   VALUES (?, ?, ?, ?)""",
                (scenario_row_id, evaluator_name, int(evaluation.passed), evaluation.reasoning),
            )

    conn.commit()
    return run_id
