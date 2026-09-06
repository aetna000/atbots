# Feature Specification: AtBots Evals

**Feature Branch**: `004-evals`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "We need to add evals into our atbots."

## Context

`003-small-model-harness` made a 4B model able to run a tool loop, and the work
turned up failures that ordinary unit tests do not describe well:

- A 1.7B model answered *"free disk space is 10 gigabytes"* without calling the
  tool. The run reported `completed`. Nothing was raised. The number was
  invented. A passing test suite said everything was fine.
- Strengthening the step instructions took recoveries from four per run to zero.
  There was no measurement that would have caught that going the other way.

Unit tests answer "is the harness correct". Evals answer "does a small model
actually succeed, how often, and how hard did the harness have to work". Both
are needed, and they cannot be the same suite: harness correctness is
deterministic, model behaviour is statistical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Deterministic Gate on Every Commit (Priority: P1)

A contributor changes the loop, the prompt, or the observation budget. Before the
change merges, a fast suite that needs no model tells them whether the harness
still recovers from every failure mode and still lands the grounded answer.

**Why this priority**: This is the regression gate. It must be fast, hermetic,
and run by default, or it will not run at all.

**Independent Test**: Run the eval suite with no model server reachable. It
completes in seconds and reports a pass or fail per scenario.

**Acceptance Scenarios**:

1. **Given** a scenario whose scripted model emits malformed decisions, an
   invented tool name, and a repeat before answering, **When** the suite runs,
   **Then** the harness still produces the grounded answer and the scenario
   passes.
2. **Given** a scripted model that answers without calling the tool that holds
   the fact, **When** the suite runs, **Then** the scenario fails on
   groundedness, naming the fabricated value.
3. **Given** no model server is running, **When** the suite runs, **Then** it
   passes; it never reaches the network.
4. **Given** a regression that makes the loop raise, **When** the suite runs,
   **Then** it fails rather than erroring out of the run.

---

### User Story 2 - A Measurement Against a Real Small Model (Priority: P1)

A maintainer wants to know whether `qwen3:4b` on a laptop actually completes
these tasks, how often, and whether a prompt change helped or hurt.

**Why this priority**: This is the question the harness exists to answer. Tier 1
cannot answer it, because a scripted model is not a model.

**Independent Test**: Run the live suite against Ollama with repetitions and get
a report of per-scenario rates and per-run metrics.

**Acceptance Scenarios**:

1. **Given** a reachable Ollama and a pulled model, **When** the live suite runs
   with N repetitions, **Then** it reports a success rate, a groundedness rate,
   and mean steps and recoveries per scenario.
2. **Given** no Ollama or an unpulled model, **When** the live suite runs,
   **Then** it skips with the reason, and never fails the default gate.
3. **Given** a recorded baseline, **When** the live suite runs, **Then** rates
   below the baseline beyond a stated tolerance are reported as regressions.
4. **Given** the same suite run twice, **When** results differ, **Then** the
   difference is reported as a rate, never as a pass/fail on a single run.

---

### User Story 3 - Groundedness Is Scored, Not Assumed (Priority: P1)

An answer that is confident, plausible, and invented must score worse than an
answer that is correct because a tool produced it.

**Why this priority**: This is the specific defect that motivated the feature and
the one most likely to recur, because it looks like success from every other
angle.

**Independent Test**: Score an answer containing a fabricated value against a
scenario whose fixture value differs, and confirm it fails.

**Acceptance Scenarios**:

1. **Given** an answer containing the fixture's value, **When** it is scored,
   **Then** groundedness passes.
2. **Given** an answer containing a plausible value the fixture never produced,
   **When** it is scored, **Then** groundedness fails and names the value.
3. **Given** a correct answer produced without calling the tool that holds the
   fact, **When** it is scored, **Then** tool coverage fails even though the
   answer is right.

---

### User Story 4 - Metrics That Track Harness Effort (Priority: P2)

A maintainer tuning the prompt or the budget can see how much work the harness
did on the model's behalf, not only whether the run ended well.

**Why this priority**: Recovery count moved 4 → 0 on a prompt change. Without it,
a change that makes the model worse but still passing is invisible.

**Independent Test**: Run a scenario whose scripted model needs three recoveries
and confirm the recorded recovery count is three.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** it is scored, **Then** steps taken,
   recoveries, tools called, and peak step-prompt size are recorded.
2. **Given** a peak step-prompt size, **When** it is reported, **Then** it can be
   compared against the configured context window.

---

### Edge Cases

- A scenario's tool raises: the run still ends with a status, and the scenario
  fails on groundedness rather than erroring.
- The live model exceeds the step budget: recorded as a failed run at a rate, not
  an exception.
- A scenario declares no expected tools: tool coverage passes trivially and only
  groundedness applies.
- A grounded value appears in the answer only as part of a larger number: matching
  MUST be on value boundaries, so `137` does not match `1370`.
- The eval dependency is absent: the suite skips with an installation message
  rather than failing collection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Evals MUST be expressed with the upstream evaluation framework, not
  a runner written in this repository.
- **FR-002**: Scenarios, fixtures, and evaluators MUST be shared by both tiers, so
  the two tiers measure the same tasks.
- **FR-003**: Tier 1 MUST run without a model server and MUST be part of the
  default verification gate.
- **FR-004**: Tier 2 MUST NOT run by default, MUST be opt-in, and MUST skip with a
  stated reason when its model is unavailable.
- **FR-005**: Tool fixtures MUST be deterministic, so the model is the only
  variable between runs.
- **FR-006**: Groundedness MUST be scored against values the fixtures actually
  produced, and MUST fail on plausible values they did not.
- **FR-007**: Tool coverage MUST be scored from the run trace, independently of
  whether the answer is correct.
- **FR-008**: Every run MUST record steps taken, recoveries, tools called, and
  peak step-prompt size.
- **FR-009**: Tier 2 MUST support repetitions and MUST report per-scenario rates
  rather than single-run outcomes.
- **FR-010**: Tier 2 MUST compare rates against a recorded baseline with an
  explicit tolerance, and MUST name any scenario that regressed.
- **FR-011**: Evaluators MUST be deterministic; no model-judged scoring in either
  tier.
- **FR-012**: The eval framework MUST be an optional dependency; `pip install
  atbots` MUST NOT install it.
- **FR-013**: Adding a scenario MUST NOT require changing evaluator or runner code.

### Key Entities

- **Scenario**: an objective, the tools available for it, the tools that must be
  called, the values a correct answer must contain, and values that would prove
  fabrication.
- **Outcome**: what one run produced — answer, status, steps, tools called,
  recoveries, peak step-prompt size.
- **Baseline**: recorded per-scenario rates from a known-good Tier 2 run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tier 1 completes in under five seconds with no network access.
- **SC-002**: A deliberately fabricated answer fails Tier 1, and the failure names
  the fabricated value.
- **SC-003**: Removing the grounding rules from the step instructions causes a
  measurable drop in Tier 2 groundedness rate.
- **SC-004**: Tier 2 reports, per scenario, a success rate, a groundedness rate,
  and mean steps and recoveries over N repetitions.
- **SC-005**: The default `pytest -q` run includes Tier 1 and excludes Tier 2.
- **SC-006**: A new scenario can be added by editing one list.

## Outcome

The first recorded Tier 2 baseline found a harness defect that Tier 1 could not:
`survives_failing_tool` scored 0.00 across every repetition, with recoveries equal
to the entire step budget. Repeat detection recorded only successful calls, so a
model that kept retrying a broken tool consumed every step. Tier 1 passed the same
scenario because its script called the tool once — only a real model, free to
choose its own next step, exposed the loop. Fixed under `003-small-model-harness`
FR-020 and FR-021.

## Assumptions

- The reference model is `qwen3:4b`; where it is not pulled, a smaller model of
  the same family is an acceptable harder case.
- Tier 2 is run by maintainers and in an optional job, not on every commit.
- Baselines are recorded by a human and committed, not regenerated automatically.
