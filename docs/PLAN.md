# Build plan

## Why this exists

Most public eval-framework tutorials stop at single-agent tool-call
accuracy. The interesting part of multi-agent systems — what gets dropped
or hallucinated when one agent hands off to another — usually isn't
covered. This project builds toward that: deterministic mock agents with
deliberately injected failure modes (dropped context, hallucinated tool
calls, timeouts), so the detection logic can be proven correct against
known ground truth before it's ever pointed at anything nondeterministic.

## Ground rules

- Mock agents first. Real Claude/OpenAI calls come later, once detection
  logic is proven deterministic — except the LLM-judge, which is
  evaluating rather than being evaluated, and may use a real API call
  earlier (see day 16).
- Mock agents are deterministic by construction: seeded, no randomness, no
  timing-dependent branching. CI should never flake.
- An LLM-judge is never CI-blocking, even after calibration. Calibration
  makes it trustworthy to *read*, not safe to *gate on* — the single most
  common failure mode in current agent-eval literature is trusting an
  unvalidated judge in a regression gate.
- Vertical slices, not layers. Every day ends with something that runs.

## Day-by-day

1. **(done)** Repo scaffold, one deterministic mock agent, one scenario,
   a runner with a hardcoded check, PASS/FAIL output. The walking
   skeleton.
2. **(done)** Scenario spec schema v1 (pydantic: role, input,
   expected_tool_calls, success_criteria) + YAML loader.
3. **(done)** Second mock agent with an injected failure mode: drops a
   required tool call.
4. Rule-based evaluator: tool-call-sequence matcher (exact/subset).
5. Rule-based evaluator: output-format validator (schema/regex).
6. Runner CLI (`harness run scenarios/*.yaml`): loads scenarios, runs the
   mock agent, applies evaluators, prints a report table. Each scenario
   runs in its own try/except so one bad scenario can't kill the whole
   suite.
7. Third mock agent that hallucinates a tool call outside its allowed
   set; add a hallucination-detection mode to the day-4 matcher (same
   evaluator, not a new class).
8. Two-agent handoff scenario spec: add `handoff_to` + `context_passed`
   as optional fields — existing scenarios stay valid, no migration.
9. Context-loss detector v1: diff the context dict passed agent→agent,
   flag missing keys.
10. Context-loss detector v2: flag hallucinated keys present on the
    receiving side but never passed.
11. Fourth mock agent that times out / partially completes; add timeout
    handling to the runner.
12. Mock tool server v1: a small local HTTP server standing in for one
    fake external API, deterministic canned responses.
13. Wire a mock agent to call the mock tool server instead of a
    hardcoded stub — first fully "live" (locally) run.
14. Second mock tool server + second agent using it, to prove the
    pattern generalizes.
15. Reproducibility pass: log every run's inputs and every agent/tool-
    server output to JSON, keyed by run id. "Replay" means re-running
    the evaluators against a logged run's outputs without re-invoking
    the agent or tool server.
16. LLM-judge scorer v1: wire a real Claude/OpenAI call to grade one
    open-ended scenario against a rubric.
17. Judge calibration: hand-label 10-15 scenario outputs, compare judge
    scores against the labels, log the agreement rate. If agreement is
    low, iterate on the rubric before moving on.
18. Judge bias checks: test for position bias and verbosity bias,
    document findings.
19. SQLite run-log schema (runs, scenarios, evaluator_results tables);
    write results from the runner into it.
20. Minimal dashboard v1 (optional): a single static page reading the
    SQLite file, showing pass-rate per agent.
21. Dashboard v2 (optional): add latency/cost per hop (needs per-call
    token/time tracking added back around day 11-13).
22. GitHub Actions CI: run the full scenario suite on every push, fail
    the build on a regression.
23. Regression gate policy: rule-based evaluators are CI-blocking; the
    LLM-judge stays advisory-only, permanently.
24. README polish + a short "what I learned" note per major module.
25. Stretch: swap one mock agent for a real Claude API call behind a
    flag, to prove the harness also works against something
    nondeterministic.

## Landscape notes (2026)

- The "handoff" is treated as the natural evaluation unit for multi-agent
  systems — dispatch correctness and scope fidelity are early indicators
  of handoff quality.
- A recent empirical taxonomy of agent failures across 1,600+ traces
  found inter-agent misalignment is a distinct, pervasive failure
  category, not just noise.
- Rule-based checks are cheap, deterministic, and never disagree with
  themselves on rerun; LLM-judge scoring earns its cost only where a rule
  genuinely can't express the target.
- Known judge failure modes to design around: position bias (favors
  whichever answer is seen first), verbosity bias (rewards longer
  answers), and treating a 100% pass rate as success (usually means the
  eval isn't hard enough).
