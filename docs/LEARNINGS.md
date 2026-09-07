# What I learned

Short, concrete notes per major piece of this project — not generic
takeaways, things that actually happened during the build. Cross-referenced
against [`PLAN.md`](PLAN.md) for which day each one came from.

## Scenario spec (`harness/schema.py`)

Designing every new field as optional and additive from day one (day 2)
meant that days 7, 8, 9, and 10 could each add a field — `allowed_tool_calls`,
`handoff_to`, `context_passed`, `expected_output_schema` — without ever
writing a migration or touching an existing scenario file. The discipline
cost nothing up front and paid off every single time a new day needed a
new field. It's easy to see why real API schemas end up "everything
optional" — this is why.

## Evaluators (`harness/evaluators/`)

The hallucination check (day 7) taught me that "a stricter version of an
existing check" and "a genuinely different question" look similar but
aren't. Subset mode asks "did the required calls happen?" and tolerates
extras; hallucination mode asks "did anything unauthorized happen?" and
is blind to what's missing. Folding them together would have produced an
evaluator that couldn't express "loose on order, strict on authorization"
— a real scenario shape. That's why it became a mode on one class instead
of a merge or a new one.

## Mock agents (`harness/mock_agent.py`)

The same bug happened twice. Day 3 and day 7's wrapper agents
(`DropsToolCallAgent`, `HallucinatesToolCallAgent`) rebuilt `AgentResult`
by hand, and when day 8 added `handoff_context`, both wrappers silently
dropped it — found and fixed on day 9. By day 21, adding `latency_ms`,
I checked every wrapper up front instead of waiting to get bitten again.
The lesson: a dataclass with optional fields isn't safe just because the
constructor has good defaults — every place that *reconstructs* one needs
auditing whenever a field gets added, and that audit doesn't happen on
its own.

## Mock tool server (`harness/mock_tool_server.py`)

`http.server`'s `serve_forever()` defaults to a 0.5-second poll interval,
so every naive start/stop cycle in the day-12 test file was quietly
eating half a second. It wasn't broken, just slow enough that nobody
would notice in one run — only across a growing test suite. Passing
`poll_interval=0.05` cut that file's runtime from 4.2s to 0.5s. "It
works" and "it's fast enough to run hundreds of times in CI" turned out
to be different bars, and the gap between them was one keyword argument
I wouldn't have found without actually timing the tests.

## Runner CLI (`harness/cli.py`)

Giving `evaluate_scenario()` an `agent=` override (day 11) — instead of
requiring every test agent to live in the shared registry — turned out
to be the single most reused piece of infrastructure in the whole
project. Days 11 through 23 all lean on it to run a specific failure-mode
agent through the *real* code path (crash isolation, evaluator
composition, everything) without polluting the registry's "every agent
here passes" guarantee. Adding one optional parameter early bought a lot
of test-writing leverage later.

## Reproducibility (`harness/run_log.py`)

`replay()` has no agent parameter. That was a deliberate choice on day
15: rather than documenting "replay never calls the agent" as a rule
someone has to remember, the function's own signature makes it
structurally impossible to violate. A comment can be ignored; a missing
parameter can't. That's a cheap trick that generalizes well beyond this
project.

## LLM-judge, calibration, and bias checks (`harness/llm_judge.py`,
`harness/calibration.py`, `harness/bias_checks.py`)

Two things stand out here. First: `claude-3-5-haiku-latest`, set on day
16, had quietly gone stale by day 21 — it doesn't appear in Anthropic's
current pricing at all. Nothing failed loudly; it would have kept
"working" (or errored obscurely) indefinitely if I hadn't gone looking
for real pricing numbers for the cost-tracking feature. Second, and more
important: it's easy for a project like this to *imply* more rigor than
it has. Several of these modules say, in their own docstrings and test
files — not just in commit messages — that the real judge has never
actually been calibrated or bias-checked against a live model. Only the
checking machinery is proven, against fake judges. Saying that plainly,
in the code itself, was more useful than a clean-looking calibration
number would have been.

## SQLite run-log and dashboard (`harness/run_db.py`, `harness/dashboard.py`)

Day 19's schema didn't include a `role` column on the `scenarios` table,
because at the time nothing needed to group by agent. Day 20's dashboard
needed exactly that query, so the column got added a day later. A
three-table schema still benefits from sketching the actual queries
you'll run against it before writing `CREATE TABLE` — "minimal" and
"complete enough for the obvious next question" aren't the same thing.

## CI (`.github/workflows/ci.yml`)

The workflow file's *first* push — creating `ci.yml` from nothing —
went through cleanly. A routine version-bump edit to that same file, one
day later, was rejected: `refusing to allow an OAuth App to create or
update workflow without 'workflow' scope`. Same file, same repo, same
token, different result. GitHub's permission model for workflow files is
the kind of thing you only discover by actually pushing, not by reading
about it beforehand — and it's a good reminder that CI infrastructure
has its own permission surface, separate from the code it's testing.

## Regression gate policy (`harness/advisory.py`)

The policy "the judge should never block CI" was already true by day 22
— nobody had wired it into `DEFAULT_EVALUATORS`. But a policy that's
only true because nobody has broken it yet isn't a policy, it's an
accident waiting for day 30. Day 23 turned it into a test
(`DEFAULT_EVALUATORS` contains no `LLMJudgeEvaluator`) and a module
(`harness/advisory.py`) whose `main()` function has no code path that
reads a verdict before returning 0. The difference between "true today"
and "structurally can't become false" is worth the extra hour.

## Live agent (`harness/live_agent.py`)

Every mock agent before this one was deterministic on purpose, which
made them easy to test but meant no evaluator had ever been proven
against output that *varies*. Writing `LiveClaudeAgent`'s test against
a real model made one thing obvious in a way a design doc never would:
you cannot assert exact string equality on anything the model says, so
every check that matters here has to be loose by construction — subset
mode instead of exact, a regex instead of an exact match. Those loose
modes existed since days 4 and 5 for other reasons (order flexibility,
partial output), but this is the day it became clear they weren't just
convenience options — they're the only way an evaluator can survive
contact with something nondeterministic at all.
