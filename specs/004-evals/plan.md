# Implementation Plan: AtBots Evals

**Branch**: `004-evals` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

## Summary

One set of scenarios, fixtures, and evaluators; two tiers that run them. Tier 1
drives the loop with scripted model behaviour and gates every commit. Tier 2
drives it with a real local model, repeats, and reports rates against a baseline.
Both are `pydantic_evals` datasets over the same `Scenario` list.

## Technical Context

**Language/Version**: Python 3.10+ (eval modules use 3.10-compatible syntax)

**Primary Dependencies**: `pydantic-evals>=2.40,<3` (optional extra), `pydantic-ai-slim[openai]>=2.40,<3`, Ollama for Tier 2 only

**Testing**: pytest; Tier 1 in the default gate, Tier 2 behind a marker

**Target Platform**: Local developer machine

**Project Type**: Single Python package plus a non-shipped `evals/` package

**Performance Goals**: Tier 1 under five seconds, no network

**Constraints**: Deterministic evaluators only; no model-judged scoring; eval
framework never a runtime dependency

## Design

### One scenario list, two task functions

`Scenario` carries the objective, the fixture tools available, the tools that
must be called, the values a grounded answer contains, and the values that prove
fabrication. `run_scenario` builds a `TaskAgent`, registers that scenario's
fixture tools, runs it, and returns an `Outcome`.

The only difference between tiers is the provider:

- **Tier 1** substitutes a `ScriptedProvider` replaying a per-scenario list of
  model behaviours, including exceptions and off-schema decisions.
- **Tier 2** uses the configured Ollama provider unchanged.

Everything downstream — evaluators, metrics, reporting — is shared. That is what
makes the two tiers comparable rather than two unrelated suites.

### Why custom evaluators

`pydantic_evals` ships `Contains`, `EqualsExpected`, `ToolCorrectness`,
`LLMJudge` and others. Two of the four metrics that matter here are not
expressible with them:

- **Groundedness** is not "contains the expected string". It is "contains the
  value the fixture produced *and* none of the plausible values it did not". The
  negative half is the whole point: the defect this feature exists to catch was a
  confident, well-formed, invented number.
- **Recovery count** is a property of the AtBots trace, which upstream evaluators
  cannot see.

`LLMJudge` and `GEval` are deliberately unused: a local-first package should not
need egress to score itself, and a 4B judge scoring a 4B agent measures noise.

### Peak prompt size

Recorded by a `RecordingProvider` that wraps whichever provider the tier uses and
notes the length of each step prompt. This is the metric that answers "does this
still fit the window" as tools and skills are added.

### Rates, not assertions, in Tier 2

`Dataset.evaluate_sync` takes `repeat`, so Tier 2 runs each scenario N times and
aggregates by `source_case_name`. A single failed run is not a failure; a rate
below the baseline minus a tolerance is. Baselines are committed by a human.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Installable package | `evals/` is not part of the wheel; `pydantic-evals` is an optional extra. |
| II. Thin layer over Pydantic AI | Upstream `pydantic_evals` owns datasets, running, concurrency, repetition, and reporting. This repo contributes scenarios and four domain evaluators it cannot express upstream. |
| III. Memory is a pluggable port | Fixtures use a stub memory runtime; no vendor is exercised. |
| IV. Tasks, skills, tools | Scenarios are ordinary tasks with ordinary tools. |
| V. Local and third-party models | Tier 2 is local Ollama and opt-in; no remote egress in either tier. |

Quality and Safety gate: "pytest in this repository is the default verification
gate" — Tier 1 joins that gate; Tier 2 explicitly does not, because a
statistical measurement cannot be a binary gate without becoming noise.

## Project Structure

```text
specs/004-evals/{spec,plan,tasks}.md

evals/
├── __init__.py
├── fixtures.py     # deterministic tools + stub memory runtime
├── scenarios.py    # the Scenario list — the one file you edit to add a case
├── harness.py      # Outcome, RecordingProvider, ScriptedProvider, run_scenario
├── evaluators.py   # Grounded, NoFabrication, ToolCoverage, Completed + metrics
├── tier1.py        # scripted dataset
├── tier2.py        # live dataset, repetitions, baseline comparison
└── baseline.json   # committed rates from a known-good run

tests/
├── test_evals_tier1.py   # default gate
└── test_evals_tier2.py   # marked `eval`, opt-in
```

**Structure Decision**: `evals/` sits outside `src/` so it is not packaged.
`setuptools.packages.find` is already scoped to `where = ["src"]`, so no
exclusion is needed.

## Complexity Tracking

| Addition | Why needed | Rejected alternative |
|---|---|---|
| Custom `Grounded` / `NoFabrication` | Upstream `Contains` cannot express "and none of these plausible values" | `Contains` alone passes the exact fabrication this feature exists to catch |
| `RecordingProvider` | Peak prompt size is not observable from the task result | Logging prompts inside `agent.py` puts eval concerns in shipped code |
| Committed baseline | Model rates drift; a fixed threshold is either too loose or flaky | Asserting a hard rate makes the suite fail on ordinary variance |
