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

## Status: Day 17 of 25 — judge calibration (built, not yet run for real)

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

```bash
pip install -e ".[dev]"
harness run
```

```bash
pytest
```

To run the LLM-judge against a real model, or run calibration for real
(optional — the rest of the suite works without either):

```bash
pip install -e ".[dev,llm-judge]"
export ANTHROPIC_API_KEY=sk-...
pytest tests/test_day16_llm_judge.py
python -m harness.calibration
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
