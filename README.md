# multi-agent-eval-harness

[![CI](https://github.com/aksharraikanti/multi-agent-eval-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/aksharraikanti/multi-agent-eval-harness/actions/workflows/ci.yml)

A multi-agent LLM eval harness, built from scratch as a learning project.

Most public eval-framework write-ups stop at single-agent tool-call accuracy.
This project goes further: deterministic mock agents with deliberately
injected failure modes (dropped context on handoff, hallucinated tool calls,
timeouts) so the harness's detection logic — including a multi-agent
handoff/context-loss detector — can be proven correct against known ground
truth before it's ever pointed at anything nondeterministic.

Built one small, working increment at a time, 25 days, one commit per day.
See [`docs/PLAN.md`](docs/PLAN.md) for the full build log and
[`docs/LEARNINGS.md`](docs/LEARNINGS.md) for what each module actually
taught along the way.

## Quickstart

```bash
pip install -e ".[dev]"
harness run      # runs the real scenario suite against the mock agents
pytest           # runs the full test suite
```

## Status: Day 25 of 25 — complete

Everything below is what's implemented. Full day-by-day history is in
[`docs/PLAN.md`](docs/PLAN.md).

| Piece | What it does |
|---|---|
| **Scenario spec** (`harness/schema.py`, `scenarios/*.yaml`) | Pydantic schema for tool-call expectations, output-format checks, and multi-agent handoff fields, loaded from YAML. |
| **Evaluators** (`harness/evaluators/`) | Rule-based checks: tool-call sequence (exact / subset / hallucination modes), output format (regex + JSON shape), context loss across a handoff (missing/mismatched + hallucinated keys). |
| **Mock agents** (`harness/mock_agent.py`) | Deterministic agents with injected failure modes — dropped/hallucinated tool calls, dropped/hallucinated handoff context, timeouts/partial completion — plus `HttpAgent`, backed by a real HTTP call to `MockToolServer` instead of a dict lookup. |
| **Runner CLI** (`harness/cli.py`, installed as `harness`) | `harness run [paths...]` runs every scenario against its registered agent, applies every evaluator, reports PASS/FAIL/TIMEOUT with per-scenario crash isolation. |
| **Reproducibility** (`harness/run_log.py`) | Record a run to JSON; replay it against evaluators later with no agent or network call involved. |
| **SQLite run-log + dashboard** (`harness/run_db.py`, `harness/dashboard.py`) | Persists every run (`runs`/`scenarios`/`evaluator_results` tables); `generate_dashboard()` renders a single static HTML file — pass rate, avg latency, judge cost — no server, no build step. |
| **LLM-judge** (`harness/llm_judge.py`) | Grades open-ended output against a scenario's rubric via a real Claude call (`claude-haiku-4-5`). Kept intentionally non-blocking — see Ground Rules. |
| **Judge calibration + bias checks** (`harness/calibration.py`, `harness/bias_checks.py`) | A 12-example hand-labeled set and agreement-rate scoring; verbosity-bias and order-independence checks. The checking *machinery* is fully tested against fake judges — **the real judge has not been calibrated or bias-checked against a live model yet.** Run `python -m harness.calibration` / `python -m harness.bias_checks` yourself to get real findings. |
| **Regression gate policy** (`harness/advisory.py`) | Rule-based evaluators are CI-blocking; the judge is advisory-only, permanently — locked in by a test, not just a comment. `python -m harness.advisory` reads the judge's opinions without ever touching the exit code. |
| **CI** (`.github/workflows/ci.yml`) | Every push/PR: install, `pytest`, `harness run`, on Python 3.11 and 3.12. No secrets required. |
| **Live agent** (`harness/live_agent.py`) | `LiveClaudeAgent` runs a real one-tool tool-use loop against a real `MockToolServer` — a real model decides whether to call the tool and how to phrase the answer. The harness's only genuinely nondeterministic agent; proves the same evaluators work against varying, not just canned, output (loose checks — `subset` mode, a regex — are what make that possible). Never wired into the default suite; gated the same way as the judge. |

## Working with the LLM-judge

Everything above runs with `pip install -e ".[dev]"` and no API key. To
exercise the judge itself, or run calibration/bias checks for real:

```bash
pip install -e ".[dev,llm-judge]"
export ANTHROPIC_API_KEY=sk-...

pytest tests/test_day16_llm_judge.py    # the judge's own test, live
pytest tests/test_day25_live_agent.py   # the live agent's own test, live
python -m harness.calibration           # agreement rate vs. hand labels
python -m harness.bias_checks           # verbosity + order-independence
python -m harness.advisory              # read judge opinions (never blocks)
```

To view the dashboard after a run:

```bash
python -m harness.dashboard runs.db dashboard.html
open dashboard.html
```

## Ground rules

- Mock agents are deterministic by construction — no real sleeping, no
  randomness — so CI runs never flake.
- The LLM-judge is never a CI-blocking gate, even after calibration.
  Calibration makes it trustworthy to *read*, not safe to *gate on*.
- Every day is a vertical slice: something runs and every test passes
  before moving to the next one.
