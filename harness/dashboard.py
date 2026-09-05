"""Day 20: minimal dashboard v1 — pass rate per agent, as a single
static HTML file with no server and no build step, generated from the
SQLite run-log (day 19).

No client-side database reading: browsers block fetch() of a local
file:// SQLite database, and pulling in sql.js (WASM) for this would be
a real dependency for what's fundamentally a GROUP BY query. Instead
the data is queried in Python and baked directly into the generated
HTML as a plain table — zero new dependencies, works when someone just
double-clicks the output file.

Aggregates across every run ever recorded in the database, not just the
latest one — the point of persisting runs at all (day 19) is comparing
across them; day 21 may add a per-run or time-series view on top.
"""

import html
import sqlite3
from pathlib import Path

from harness.run_db import connect


def _query_pass_rate_by_role(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    return conn.execute(
        "SELECT role, COUNT(*) AS total, SUM(passed) AS passed FROM scenarios GROUP BY role ORDER BY role"
    ).fetchall()


def _render_html(rows: list[tuple[str, int, int]], run_count: int) -> str:
    table_rows = "".join(
        f"<tr><td>{html.escape(role)}</td><td>{passed}/{total}</td><td>{(passed / total if total else 0):.0%}</td></tr>"
        for role, total, passed in rows
    ) or '<tr><td colspan="3">No runs recorded yet.</td></tr>'

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
  <thead><tr><th>Agent role</th><th>Passed / Total</th><th>Pass rate</th></tr></thead>
  <tbody>{table_rows}</tbody>
</table>
</body>
</html>
"""


def generate_dashboard(db_path: Path | str, output_path: Path | str) -> None:
    conn = connect(db_path)
    rows = _query_pass_rate_by_role(conn)
    run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    Path(output_path).write_text(_render_html(rows, run_count))


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "runs.db"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "dashboard.html"
    generate_dashboard(db_path, output_path)
    print(f"Dashboard written to {output_path}")
