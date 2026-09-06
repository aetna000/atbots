# Tasks: AtBots Evals

**Feature**: `004-evals` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup

- [X] T001 Add `evals` optional dependency group (`pydantic-evals>=2.40,<3`) and
      include it in `dev` in `pyproject.toml`.
- [X] T002 Register the `eval` pytest marker and deselect it by default in
      `pyproject.toml`.

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Deterministic fixture tools and a stub memory runtime in
      `evals/fixtures.py`.
- [X] T004 `Scenario` type and the scenario list in `evals/scenarios.py`.
- [X] T005 `Outcome`, `ScriptedProvider`, `RecordingProvider`, and
      `run_scenario` in `evals/harness.py`.

## Phase 3: User Story 3 - Groundedness Is Scored (P1)

- [X] T006 [US3] `Grounded` evaluator: every fixture value present, matched on
      value boundaries so `137` does not match `1370`.
- [X] T007 [US3] `NoFabrication` evaluator: fails and names any forbidden value.
- [X] T008 [US3] `ToolCoverage` evaluator scored from the trace, independent of
      answer correctness.

## Phase 4: User Story 1 - Deterministic Gate (P1) MVP

- [X] T009 [US1] Tier 1 dataset over the scenarios with scripted behaviour in
      `evals/tier1.py`.
- [X] T010 [US1] Adversarial scripts: malformed decision, invented tool name,
      repeated call, oversized tool result.
- [X] T011 [US1] A negative-control scenario whose scripted model fabricates a
      value, proving the suite detects it.
- [X] T012 [US1] `tests/test_evals_tier1.py` in the default gate; no network.

## Phase 5: User Story 4 - Harness Effort Metrics (P2)

- [X] T013 [US4] Record steps, recoveries, tools called, and peak step-prompt
      size as metrics on every run.

## Phase 6: User Story 2 - Live Model Measurement (P1)

- [X] T014 [US2] Tier 2 dataset with `repeat=N` in `evals/tier2.py`.
- [X] T015 [US2] Aggregate per-scenario rates by `source_case_name`.
- [X] T016 [US2] Baseline comparison with an explicit tolerance; name regressions.
- [X] T017 [US2] Skip with a stated reason when Ollama or the model is absent.
- [X] T018 [US2] `tests/test_evals_tier2.py` behind the `eval` marker.
- [X] T019 [US2] A `python -m evals.tier2` entry point that prints the report.

## Phase 7: Polish & Verification

- [ ] T020 Record `evals/baseline.json` from a live run.
- [X] T021 Confirm the default gate includes Tier 1 and excludes Tier 2.
- [ ] T022 Verify SC-003: removing the grounding rules drops the Tier 2
      groundedness rate.
- [X] T023 Document both tiers in `README.md`.

## Dependencies & Execution Order

- Phase 2 blocks everything.
- US3 (Phase 3) blocks both tiers, since both score with those evaluators.
- US1 (Phase 4) is the MVP and ships independently of Tier 2.
- US2 (Phase 6) needs Phases 2, 3, and 5.
