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

## Status: Day 8 — two-agent handoff scenario spec

- `AgentResult` gains an optional `handoff_context` field — what an
  orchestrator actually hands off to a worker agent. `ScenarioSpec`'s
  `handoff_to`/`context_passed` fields (reserved since day 2) get their
  first real use: `scenarios/handoff_create_ticket.yaml` plus a
  registered `orchestrator` mock agent whose `handoff_context` matches
  what the scenario expects. No detector yet — days 9-10 diff the two
- `ToolCallSequenceEvaluator` gains `mode="hallucination"`: every actual
  tool call must appear in the scenario's allow-list
  (`allowed_tool_calls`, defaulting to `expected_tool_calls` when unset).
  It's a separate mode from `subset` on purpose — `subset` explicitly
  tolerates extra calls, so it alone would never catch an unauthorized
  one (e.g. a `delete_ticket` call slipped into a read-only search)
- A third mock agent, `HallucinatesToolCallAgent`, wraps a correct script
  and deterministically appends one tool call that was never scripted
- `harness/cli.py`, installed as the `harness` command: `harness run
  [paths...]` walks any mix of directories and scenario files (defaults
  to `scenarios/`), runs each one against its registered agent
  (`harness/agent_registry.py`), applies every evaluator, and prints a
  report. Each scenario runs in its own try/except — an unregistered
  role, an agent with no scripted response, or an evaluator bug is
  caught and reported as a FAIL, not an aborted run
- `harness/evaluators/output_format.py`: `OutputFormatEvaluator` checks
  an agent's textual output against two independent, opt-in checks —
  `expected_output_pattern` (regex) and `expected_output_schema` (a
  minimal JSON shape: top-level keys and their expected types). A
  scenario that sets neither trivially passes
- A deterministic mock agent (`harness/mock_agent.py`: `CannedAgent`) and
  one that wraps any script and deterministically drops one required
  tool call (`DropsToolCallAgent`)
- A pydantic scenario schema (`harness/schema.py`) with handoff fields
  already reserved (optional) for the multi-agent work later
- Scenarios live as YAML (`scenarios/*.yaml`), loaded via
  `harness/scenario_loader.py`

```bash
pip install -e ".[dev]"
harness run
```

```bash
pytest
```

## Roadmap

Rule-based tool-call evaluators, a real scenario schema, multi-agent
handoff scenarios, a context-loss detector, mock tool servers for
reproducible runs, an LLM-judge with a documented calibration step, a run
log, a minimal dashboard, and CI. See `docs/PLAN.md` for the day-by-day
order and the reasoning behind it.
