# multi-agent-eval-harness

A multi-agent LLM eval harness, built from scratch as a learning project.

Most public eval-framework write-ups stop at single-agent tool-call accuracy.
This project goes further: deterministic mock agents with deliberately
injected failure modes (dropped context on handoff, hallucinated tool calls,
timeouts) so the harness's detection logic — including a multi-agent
handoff/context-loss detector — can be proven correct against known ground
truth before it's ever pointed at anything nondeterministic.

Built one small, working increment at a time. See [`docs/PLAN.md`](docs/PLAN.md)
for the full day-by-day build log.

## Status: Day 21 of 25 — dashboard v2 (latency + judge cost)

Full day-by-day history (what shipped, why, and what it's for) lives in
[`docs/PLAN.md`](docs/PLAN.md). Current capabilities:

- **Scenario spec** (`harness/schema.py`, `scenarios/*.yaml`): pydantic
  schema covering tool-call expectations, output-format checks, and
  multi-agent handoff fields, loaded from YAML.
- **Evaluators** (`harness/evaluators/`): rule-based checks for tool-call
  sequences (exact / subset / hallucination modes), output format (regex
  + JSON shape), and context loss across a handoff (missing/mismatched
  and hallucinated keys) — plus an LLM-judge (`harness/llm_judge.py`) for
  open-ended rubrics, kept intentionally non-blocking (see Ground Rules
  below).
- **Mock agents** (`harness/mock_agent.py`): deterministic agents with
  injected failure modes — dropped tool calls, hallucinated tool calls,
  dropped/hallucinated handoff-context keys, timeouts/partial
  completion — plus `HttpAgent`, which gets its result from a real HTTP
  call to a `MockToolServer` (`harness/mock_tool_server.py`) instead of a
  dict lookup.
- **Runner CLI** (`harness/cli.py`, installed as `harness`): `harness run
  [paths...]` walks scenarios, runs each against its registered agent,
  applies every evaluator, and reports PASS/FAIL/TIMEOUT with
  per-scenario crash isolation.
- **Reproducibility** (`harness/run_log.py`): record a run to JSON,
  replay it against evaluators later with no agent or network call
  involved.
- **Judge calibration** (`harness/calibration.py`,
  `harness/calibration_dataset.py`): a 12-example hand-labeled set and a
  `calibrate()` function that reports the judge's agreement rate against
  those labels. The calibration *math* is tested against a scripted fake
  judge — **the real judge has not actually been calibrated yet**,
  because that requires a live `ANTHROPIC_API_KEY` and a run of
  `python -m harness.calibration` that nobody has done. Treat the judge
  as unvalidated until that changes.
- **Judge bias checks** (`harness/bias_checks.py`): `check_verbosity_bias()`
  (paired short/verbose outputs of matched correctness — flags the judge
  if it disagrees between them) and `check_order_independence()`, an
  analog of position bias adapted for a single-verdict-per-call judge
  with no pairwise comparison and no shared state. Both are proven
  against fake judges (an honest one, and two deliberately biased ones)
  — **the real judge has not been checked for either bias yet**. No
  findings exist until `python -m harness.bias_checks` is run for real.
- **SQLite run-log** (`harness/run_db.py`): `connect()` creates a
  three-table schema (`runs`, `scenarios`, `evaluator_results`) and
  `write_run()` persists a whole suite run into it, down to individual
  evaluator verdicts per scenario — not just the aggregated pass/fail
  `run_suite()` already gave you.
- **Dashboard** (`harness/dashboard.py`): `generate_dashboard(db_path,
  output_path)` writes a single self-contained static HTML file — no
  server, no build step, no client-side database library — showing pass
  rate, average latency, and total judge cost, grouped by agent role and
  aggregated across every run recorded in the SQLite log. Latency
  (`AgentResult.latency_ms`) is only ever measured by `HttpAgent`'s real
  wall-clock timing, never fabricated for an instant mock agent; judge
  cost (`EvaluationResult.cost_usd`) is computed from the real
  `usage.input_tokens`/`output_tokens` on an actual API response. Both
  render as `n/a` / "no cost recorded yet" rather than a made-up number
  when the data doesn't exist — which, honestly, it mostly doesn't yet
  in this project's own database.
  - **Found and fixed while pricing this:** the judge's model id
    (`claude-3-5-haiku-latest`, set on day 16) isn't in Anthropic's
    current pricing table at all — it looks retired. Now
    `claude-haiku-4-5` ($1.00 / $5.00 per 1M input/output tokens),
    checked via the claude-api skill rather than trusted from memory.

```bash
python -m harness.dashboard runs.db dashboard.html
open dashboard.html
```

```bash
pip install -e ".[dev]"
harness run
```

```bash
pytest
```

To run the LLM-judge against a real model, or run calibration/bias
checks for real (optional — the rest of the suite works without any of
this):

```bash
pip install -e ".[dev,llm-judge]"
export ANTHROPIC_API_KEY=sk-...
pytest tests/test_day16_llm_judge.py
python -m harness.calibration
python -m harness.bias_checks
```

## Ground rules

- Mock agents are deterministic by construction — no real sleeping, no
  randomness — so CI runs never flake.
- The LLM-judge is never a CI-blocking gate, even after day 17's
  calibration step. Calibration makes it trustworthy to *read*, not safe
  to *gate on*.
- Every day is a vertical slice: something runs and every test passes
  before moving to the next one. See `docs/PLAN.md` for the full
  day-by-day order and reasoning.
