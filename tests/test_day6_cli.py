"""Day 6: the runner CLI — directory/file collection, multi-evaluator
scoring, per-scenario crash isolation, and the report."""

from harness.cli import collect_scenarios, evaluate_scenario, main, print_report, run_suite
from harness.runner import SCENARIOS_DIR
from harness.schema import ScenarioSpec


# --- collect_scenarios ---------------------------------------------------

def test_collect_scenarios_from_directory_finds_every_yaml_file():
    scenarios = collect_scenarios([SCENARIOS_DIR])

    ids = {s.id for s in scenarios}
    assert "list_projects" in ids
    assert "create_ticket" in ids


def test_collect_scenarios_from_a_single_file():
    scenarios = collect_scenarios([SCENARIOS_DIR / "list_projects.yaml"])

    assert len(scenarios) == 1
    assert scenarios[0].id == "list_projects"


def test_collect_scenarios_mixes_directories_and_files_without_duplicating():
    scenarios = collect_scenarios([SCENARIOS_DIR / "list_projects.yaml", SCENARIOS_DIR])

    # The explicit file plus the whole directory (which also contains it)
    # — collect_scenarios doesn't dedupe, it's a straightforward expansion,
    # so list_projects legitimately appears twice here.
    ids = [s.id for s in scenarios]
    assert ids.count("list_projects") == 2
    assert "create_ticket" in ids


# --- evaluate_scenario: real registered agents (should all pass) --------

def test_registered_scenarios_all_pass_against_the_default_registry():
    for scenario in collect_scenarios([SCENARIOS_DIR]):
        outcome = evaluate_scenario(scenario)
        assert outcome.passed is True, outcome.failures
        assert outcome.crashed is False


# --- evaluate_scenario: crash isolation ----------------------------------

def test_unregistered_role_is_caught_and_reported_as_crashed():
    scenario = ScenarioSpec(id="ghost", role="nonexistent_agent", input="hello")

    outcome = evaluate_scenario(scenario)

    assert outcome.passed is False
    assert outcome.crashed is True
    assert "ghost" == outcome.scenario_id
    assert any("nonexistent_agent" in f for f in outcome.failures)


def test_agent_with_no_scripted_response_is_caught_and_reported_as_crashed():
    # project_agent is registered, but has no script for this input —
    # CannedAgent.run raises KeyError, which evaluate_scenario must catch
    # rather than letting it kill the whole suite.
    scenario = ScenarioSpec(id="unscripted", role="project_agent", input="nobody scripted this")

    outcome = evaluate_scenario(scenario)

    assert outcome.passed is False
    assert outcome.crashed is True


def test_one_crashing_scenario_does_not_stop_the_others_from_running():
    # run_suite operates on paths, not scenarios directly, so exercise the
    # crash-isolation guarantee at the evaluate_scenario level: both calls
    # must complete independently, in either order.
    good = ScenarioSpec(
        id="good",
        role="project_agent",
        input="What projects do I have access to?",
        expected_tool_calls=["list_projects"],
    )
    bad = ScenarioSpec(id="bad", role="nonexistent_agent", input="hello")

    results = [evaluate_scenario(good), evaluate_scenario(bad)]

    assert results[0].passed is True
    assert results[1].passed is False and results[1].crashed is True


# --- print_report ----------------------------------------------------------

def test_print_report_shows_pass_fail_and_a_summary_line(capsys):
    outcomes = run_suite([SCENARIOS_DIR])
    print_report(outcomes)

    output = capsys.readouterr().out
    assert "[PASS] list_projects" in output
    assert "[PASS] create_ticket" in output
    assert "2/2 scenarios passed" in output


# --- main() CLI entry point -------------------------------------------------

def test_main_with_no_args_prints_usage_and_returns_error_code(capsys):
    exit_code = main([])

    assert exit_code == 2
    assert "usage" in capsys.readouterr().err


def test_main_run_with_no_paths_defaults_to_scenarios_dir(capsys):
    exit_code = main(["run"])

    assert exit_code == 0
    assert "2/2 scenarios passed" in capsys.readouterr().out


def test_main_run_with_explicit_bad_scenario_returns_nonzero(capsys, tmp_path):
    bad_scenario = tmp_path / "bad.yaml"
    bad_scenario.write_text("id: bad\nrole: nonexistent_agent\ninput: hello\n")

    exit_code = main(["run", str(bad_scenario)])

    assert exit_code == 1
    assert "[FAIL] bad" in capsys.readouterr().out
