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

## Status: Day 3 — a mock agent with an injected failure mode

- A deterministic mock agent (`harness/mock_agent.py`: `CannedAgent`) and
  a second one that wraps any script and deterministically drops one
  required tool call (`DropsToolCallAgent`) — the first proof that the
  runner actually catches a realistic failure, not just a hand-picked
  wrong scenario
- A pydantic scenario schema (`harness/schema.py`) with handoff fields
  already reserved (optional) for the multi-agent work later
- Scenarios live as YAML (`scenarios/*.yaml`), loaded via
  `harness/scenario_loader.py`
- A runner that loads a scenario, runs the agent, checks its tool calls
  against what's expected, and prints PASS/FAIL (`harness/runner.py`)

```bash
python3 -m harness.runner
```

```bash
pip install -e ".[dev]"
pytest
```

## Roadmap

Rule-based tool-call evaluators, a real scenario schema, multi-agent
handoff scenarios, a context-loss detector, mock tool servers for
reproducible runs, an LLM-judge with a documented calibration step, a run
log, a minimal dashboard, and CI. See `docs/PLAN.md` for the day-by-day
order and the reasoning behind it.
