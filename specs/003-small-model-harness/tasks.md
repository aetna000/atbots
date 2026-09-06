# Tasks: Small-Model Task Harness

**Feature**: `003-small-model-harness` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Format: `[ID] [P?] [Story] Description`

`[P]` marks tasks with no shared file and no ordering dependency.

## Path Conventions

Package source is `src/atbots/`. Tests are `tests/`.

---

## Phase 1: Setup

- [X] T001 Confirm the installed Pydantic AI exposes `output_type`, `retries`,
      and `model_settings` on `Agent` (verified: 1.107.5).
- [X] T002 Measure Ollama context behaviour across the OpenAI-compatible
      endpoint, the native endpoint, and a derived tag; record results in
      `plan.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Add `TaskStep` output type in `src/atbots/steps.py`, with the
      JSON Schema derived from it for the deterministic provider.
- [X] T004 Add configuration in `src/atbots/config.py`: `ProviderConfig.num_ctx`,
      and `AtBotConfig.step_retries`, `observation_char_limit`,
      `observation_window`. All defaulted; none required.
- [X] T005 Extend the provider protocol in `src/atbots/providers/base.py` with an
      optional `output_type`.

---

## Phase 3: User Story 1 - A 4B Model Completes a Tool Loop (P1) MVP

- [X] T006 [US1] Request the step decision via `output_type=TaskStep` and
      `retries=step_retries` in `src/atbots/providers/pydantic_ai.py`.
- [X] T006a [US1] Request it as `NativeOutput`, not upstream's default tool mode,
      which Ollama rejects with `400 invalid message content type: <nil>`; fall
      back once and permanently to `PromptedOutput` per provider instance.
- [X] T006b [US1] Reject an unactionable decision inside `TaskStep` validation so
      the correction costs a model retry rather than a step, in
      `src/atbots/steps.py`.
- [X] T006c [US1] State in the step instructions that every fact in an answer
      comes from the observations, and push a toolless finish back once when a
      permitted tool has never succeeded (`finish_nudges`), in
      `src/atbots/agent.py`.
- [X] T007 [US1] Strip inline reasoning tags from text output in
      `src/atbots/providers/pydantic_ai.py` for non-Ollama OpenAI-compatible
      servers that inline them.
- [X] T008 [US1] Accept and ignore `output_type` in
      `src/atbots/providers/local.py` so the fallback still satisfies the protocol.
- [X] T009 [US1] Convert model-call and decision failures into recovery
      observations in `src/atbots/agent.py` instead of raising.
- [X] T010 [US1] Convert unknown, unpermitted, and destructive tool names into
      recovery observations naming the available tools, in `src/atbots/agent.py`.
- [X] T011 [US1] Convert tool-handler exceptions into failed observations in
      `src/atbots/agent.py`.
- [X] T012 [US1] Guarantee `run()` returns a result with a trace on every path.

---

## Phase 4: User Story 2 - The Model Gets Its Context Window (P1)

- [X] T013 [US2] Implement idempotent derived-tag provisioning in
      `src/atbots/providers/ollama_ctx.py`: probe the existing tag, create
      `<model>-atbots-ctx<N>` from it with `num_ctx`, cache the outcome.
- [X] T014 [US2] Use the provisioned tag for inference in
      `src/atbots/providers/pydantic_ai.py`, only for `kind == "ollama"`.
- [X] T015 [US2] Pass `kind`, `num_ctx`, and `step_retries` through
      `src/atbots/providers/router.py`.
- [X] T016 [US2] Degrade to the unprovisioned tag with a recorded reason when
      provisioning fails; never fail the task.
- [X] T017 [US2] Report the effective window and provisioning state in provider
      status, and add `--num-ctx` to `atbots init` in `src/atbots/cli.py`.

---

## Phase 5: User Story 3 - Observations Stay Inside the Budget (P2)

- [X] T018 [US3] Take the truncation limit from configuration at every call site
      in `src/atbots/agent.py`, and lower the `guard_tool_result` default from
      20,000 to 2,000 characters in `src/atbots/capabilities.py`. The default is
      changed rather than preserved because the loop is its only caller and the
      old value is itself the defect.
- [X] T019 [US3] Apply `observation_char_limit` to every recorded observation and
      retain only `observation_window` most recent ones, stating the omission, in
      `src/atbots/agent.py`.
- [X] T020 [US3] Compact the step prompt so tool descriptions and instructions
      cost less of the window.

---

## Phase 6: User Story 4 - The Loop Does Not Spin (P3)

- [X] T021 [US4] Detect a repeated identical tool call within a run and answer it
      from the earlier observation, in `src/atbots/agent.py`.

---

## Phase 7: Readiness Reporting

- [X] T026 Report a provider whose model is not pulled as unavailable, with the
      `ollama pull` command as the reason, in
      `src/atbots/providers/pydantic_ai.py` and `ollama_ctx.model_installed`.
- [X] T027 Surface `unavailable_reason` in provider status in
      `src/atbots/providers/router.py`.
- [X] T028 End a run with `provider_error` and the provider's own message after
      `provider_failure_limit` consecutive provider failures, in
      `src/atbots/agent.py`.

## Phase 8: Repeat Detection Across Failures

Found by the `004-evals` Tier 2 suite: `survives_failing_tool` scored 0.00 with
recoveries equal to the whole step budget, because repeat detection only recorded
successful calls.

- [X] T029 Record every tool call in the repeat index — succeeded, failed, and
      rejected alike — and tell the model that retrying will not help, in
      `src/atbots/agent.py`.
- [X] T030 Treat a failed or rejected call as an attempt for the toolless-finish
      push-back, so the model is not aimed at a tool that already raised.
- [X] T031 Regression tests for a repeatedly failing tool, a repeatedly invented
      tool name, and an unchanged successful repeat.
- [X] T032 Cap a tool by failure count (`tool_failure_limit`, default 2), since a
      model that varies its arguments walks past the argument-keyed repeat index.
- [X] T033 Regression tests for varying arguments and for a working tool that must
      never be capped.

## Phase 9: Polish & Verification

- [X] T022 Add `tests/test_small_model_harness.py` covering: malformed decisions,
      unknown tool names, tool exceptions, step-budget exhaustion, oversized
      observations, observation windowing, repeated calls, and derived-tag naming
      and idempotence.
- [X] T023 Run the full pytest suite and confirm pre-existing tests still pass.
- [X] T024 Verify end to end against live Ollama that the configured window is in
      force and a real small model completes a tool loop. Result with
      `qwen3:1.7b`: served at 8192 on a derived tag, tool called, answer taken
      from the tool result, two steps, no recoveries.
- [X] T025 Document the small-model settings in `README.md`.

---

## Dependencies & Execution Order

- Phase 2 blocks everything else.
- US1 (Phase 3) is the MVP and is independently shippable.
- US2 (Phase 4) is independent of US1 and independently shippable.
- US3 (Phase 5) and US4 (Phase 6) both edit `agent.py` after US1 lands.
- Phase 7 runs last.

### Parallel Opportunities

- T003 and T004 are `[P]` with respect to each other.
- T013 (`ollama_ctx.py`) is `[P]` against all of Phase 3.

## Implementation Strategy

Ship US1 first: it removes the crash. US2 next: it removes the silent 4096-token
ceiling that makes everything else pointless. US3 and US4 are hardening that make
long runs survivable.
