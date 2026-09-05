"""Day 20: minimal dashboard v1 — a static HTML file, no server, no
build step, generated from the SQLite run-log."""

from harness.cli import run_suite, ScenarioOutcome
from harness.dashboard import generate_dashboard
from harness.run_db import connect, write_run
from harness.runner import SCENARIOS_DIR


def test_generate_dashboard_writes_an_html_file(tmp_path):
    conn = connect(tmp_path / "runs.db")
    write_run(conn, [ScenarioOutcome("a", passed=True, role="agent_a")])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(tmp_path / "runs.db", output_path)

    assert output_path.exists()
    content = output_path.read_text()
    assert "<html>" in content
    assert "multi-agent-eval-harness" in content


def test_dashboard_shows_pass_rate_grouped_by_role(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, [
        ScenarioOutcome("a", passed=True, role="ticket_agent"),
        ScenarioOutcome("b", passed=False, role="ticket_agent"),
        ScenarioOutcome("c", passed=True, role="search_agent"),
    ])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)
    content = output_path.read_text()

    assert "ticket_agent" in content
    assert "1/2" in content  # ticket_agent: 1 passed of 2
    assert "50%" in content
    assert "search_agent" in content
    assert "1/1" in content
    assert "100%" in content


def test_dashboard_aggregates_across_multiple_runs(tmp_path):
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, [ScenarioOutcome("a", passed=True, role="ticket_agent")])
    write_run(conn, [ScenarioOutcome("a", passed=False, role="ticket_agent")])

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)
    content = output_path.read_text()

    assert "1/2" in content  # 1 pass across the 2 recorded runs
    assert "Aggregated across 2 recorded run(s)" in content


def test_dashboard_handles_an_empty_database_without_crashing(tmp_path):
    db_path = tmp_path / "empty.db"
    connect(db_path)  # creates schema, no data

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)

    assert "No runs recorded yet." in output_path.read_text()


def test_role_names_are_html_escaped():
    from harness.dashboard import _render_html

    html_out = _render_html(
        [("<script>alert(1)</script>", 1, 1, None)],
        run_count=1,
        total_cost=None,
        judged_call_count=0,
    )

    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


# --- integration: the real scenario suite, end to end ----------------------

def test_dashboard_against_the_real_scenario_suite(tmp_path):
    outcomes = run_suite([SCENARIOS_DIR])
    db_path = tmp_path / "runs.db"
    conn = connect(db_path)
    write_run(conn, outcomes)

    output_path = tmp_path / "dashboard.html"
    generate_dashboard(db_path, output_path)
    content = output_path.read_text()

    # Every registered role should show up, and today every scenario
    # passes (see test_day6_cli.py), so every row should read "N/N" and
    # "100%".
    roles = {outcome.role for outcome in outcomes}
    for role in roles:
        assert role in content
    assert content.count("100%") == len(roles)
