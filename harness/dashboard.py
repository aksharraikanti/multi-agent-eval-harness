"""Day 20-21: dashboard — pass rate, latency, and judge cost, as a
single static HTML file with no server and no build step, generated
from the SQLite run-log (day 19).

No client-side database reading: browsers block fetch() of a local
file:// SQLite database, and pulling in sql.js (WASM) for this would be
a real dependency for what's fundamentally a couple of GROUP BY
queries. Instead the data is queried in Python and baked directly into
the generated HTML as plain tables — zero new dependencies, works when
someone just double-clicks the output file.

Aggregates across every run ever recorded in the database, not just the
latest one — the point of persisting runs at all (day 19) is comparing
across them.

Day 21 adds two columns of data that mostly won't exist yet in this
project's own database: avg latency is only ever recorded by HttpAgent
(day 13), and judge cost only by a real LLMJudgeEvaluator call (day 16),
which per docs/PLAN.md hasn't actually been run against the real model.
Both render as "n/a" / a zero-call message rather than a fabricated
number when the data isn't there.
"""

import html
import sqlite3
from pathlib import Path

from harness.run_db import connect


def _query_pass_rate_by_role(conn: sqlite3.Connection) -> list[tuple[str, int, int, float | None]]:
    return conn.execute(
        """SELECT role, COUNT(*) AS total, SUM(passed) AS passed, AVG(latency_ms) AS avg_latency_ms
           FROM scenarios GROUP BY role ORDER BY role"""
    ).fetchall()


def _query_judge_cost(conn: sqlite3.Connection) -> tuple[float | None, int]:
    total_cost, call_count = conn.execute(
        "SELECT SUM(cost_usd), COUNT(cost_usd) FROM evaluator_results WHERE cost_usd IS NOT NULL"
    ).fetchone()
    return total_cost, call_count


def _render_html(
    rows: list[tuple[str, int, int, float | None]],
    run_count: int,
    total_cost: float | None,
    judged_call_count: int,
) -> str:
    table_rows = "".join(
        "<tr><td>{role}</td><td>{passed}/{total}</td><td>{rate:.0%}</td><td>{latency}</td></tr>".format(
            role=html.escape(role),
            passed=passed,
            total=total,
            rate=(passed / total if total else 0),
            latency=(f"{avg_latency_ms:.0f} ms" if avg_latency_ms is not None else "n/a"),
        )
        for role, total, passed, avg_latency_ms in rows
    ) or '<tr><td colspan="4">No runs recorded yet.</td></tr>'

    cost_line = (
        f"Total judge cost: ${total_cost:.4f} across {judged_call_count} judged call(s)."
        if judged_call_count
        else "No judge cost recorded yet (the LLM-judge hasn't been run against a real model in this database)."
    )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>multi-agent-eval-harness dashboard</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; background: #fafafa; }}
  h1 {{ font-size: 1.25rem; }}
  table {{ border-collapse: collapse; margin-top: 1rem; }}
  th, td {{ padding: 0.5rem 1rem; border-bottom: 1px solid #ddd; text-align: left; }}
  th {{ color: #666; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
  .subtitle {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>multi-agent-eval-harness &mdash; pass rate by agent</h1>
<p class="subtitle">Aggregated across {run_count} recorded run(s).</p>
<table>
  <thead><tr><th>Agent role</th><th>Passed / Total</th><th>Pass rate</th><th>Avg latency</th></tr></thead>
  <tbody>{table_rows}</tbody>
</table>
<p class="subtitle">{html.escape(cost_line)}</p>
</body>
</html>
"""


def generate_dashboard(db_path: Path | str, output_path: Path | str) -> None:
    conn = connect(db_path)
    rows = _query_pass_rate_by_role(conn)
    run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    total_cost, judged_call_count = _query_judge_cost(conn)

    Path(output_path).write_text(_render_html(rows, run_count, total_cost, judged_call_count))


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "runs.db"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "dashboard.html"
    generate_dashboard(db_path, output_path)
    print(f"Dashboard written to {output_path}")
