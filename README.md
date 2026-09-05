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

## Status: Day 15 — reproducibility: record and replay a run

- `harness/run_log.py`: `record_run()` captures a scenario + its
  `AgentResult` as a JSON-serializable `RunRecord`; `write_run_log()` /
  `load_run_log()` round-trip it to/from disk; `replay()` re-runs
  evaluators against a logged run without invoking the agent or any
  tool server again. That guarantee is structural, not a runtime
  check — `replay(record, evaluators)` has no agent parameter, so
  there's nothing in it that could make a network call even by
  accident. Useful for iterating on evaluator logic against a fixed,
  known trace instead of re-running (possibly costly, network-bound,
  or nondeterministic) agents every time
- A second `MockToolServer`/`HttpAgent` pair, backing a completely
  different fake API (ticket lookup instead of doc search), using zero
  new code — same two classes from days 12-13. Tests run both pairs
  simultaneously on independently OS-assigned ports and confirm they
  don't interfere, plus a negative test (pointing the wrong agent's
  script at the wrong server) to confirm a mismatch fails cleanly
  instead of silently passing
- `HttpAgent` (`harness/mock_agent.py`): the first agent whose
  `AgentResult` comes from an actual HTTP round-trip to a
  `MockToolServer` instead of a dict lookup. A non-2xx response or a
  dead server propagates as a real exception rather than being
  swallowed — the CLI's existing crash-isolation (day 6) and the
  `agent=` override (day 11) already know what to do with it, so no new
  machinery was needed to run it through the real `evaluate_scenario`
  path end to end. Not in the default registry yet — this is a
  demonstration that the pipeline works against something live, not a
  registry-wide switch
- `harness/mock_tool_server.py`: `MockToolServer`, a small local HTTP
  server (stdlib `http.server`, no new dependency) with deterministic,
  pre-scripted responses keyed by `(method, path)` — a stand-in for a
  real external API so a scenario can exercise a genuine HTTP call
  without network access or a live account. An unscripted request gets
  a 404 with a JSON error body, the HTTP equivalent of `CannedAgent`'s
  `KeyError`. Not wired into any agent yet — that's day 13
- A fourth mock agent, `TimesOutAgent`: with `partial_after=None` (the
  default) it raises `AgentTimeoutError` instead of returning anything —
  a total timeout. With `partial_after=N` it returns a result truncated
  to the first N tool calls — a timeout that cut the agent off
  mid-execution, which needs no special handling since
  `ToolCallSequenceEvaluator` already fails a short call list
- `harness/cli.py`'s `evaluate_scenario` catches `AgentTimeoutError`
  distinctly from a generic crash — `ScenarioOutcome.timed_out` and a
  `[TIMEOUT]` report status, since a timeout is a meaningful outcome an
  eval harness needs to surface clearly, not a bug in the harness
  itself. It also now accepts an explicit `agent=` override so tests can
  exercise a failure-mode agent through the real evaluate_scenario path
  without polluting the "always passes" registry
- `ContextLossEvaluator` gains `check_hallucinated_keys` (opt-in, like
  `ToolCallSequenceEvaluator`'s modes): on top of v1's missing/mismatched
  check, it flags any handoff-context key that was never part of
  `context_passed` — an orchestrator inventing information rather than
  losing it. `HallucinatesContextKeyAgent` simulates that. Wired into
  the CLI's default evaluator set (`check_hallucinated_keys=True`),
  since the CLI's whole point is applying every evaluator
- `harness/evaluators/context_loss.py`: `ContextLossEvaluator` diffs a
  scenario's `context_passed` (ground truth) against the orchestrator's
  actual `AgentResult.handoff_context`, flagging keys that are missing
  or have the wrong value. `DropsContextKeyAgent` simulates a real
  dropped-context failure to run it against
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
