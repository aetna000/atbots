# Feature Specification: Small-Model Task Harness

**Feature Branch**: `003-small-model-harness`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "Loops for AtBots to work for small models like qwen3:4b."

## Context

AtBots already defaults to `qwen3:4b` over local Ollama, and its task loop already
avoids native tool-calling in favour of one small JSON decision per step. That is
the right shape for a 4B model. It fails in practice for four measurable reasons,
all confirmed against a live Ollama on this machine:

1. **The context window is silently 4096 tokens.** Ollama's OpenAI-compatible
   endpoint ignores `options.num_ctx`; only a model whose own parameters carry
   `num_ctx` loads at a larger window. A 4B model advertised as 32k runs at 4k.
2. **One malformed step ends the run.** The loop raises on an unparsable or
   off-schema decision. Small models produce those regularly.
3. **A hallucinated tool name ends the run.** Tool lookup raises out of the loop
   instead of telling the model it guessed wrong.
4. **One tool result can exhaust the window.** A single observation may be 20,000
   characters, and observations accumulate across every step.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A 4B Model Completes a Tool Loop (Priority: P1)

A developer with Ollama and `qwen3:4b` on a laptop runs an AtBots task that needs
one or more tool calls. The task completes with a useful answer instead of
aborting on the first schema slip or invented tool name.

**Why this priority**: This is the reported failure. Without it, the local-first
default in the constitution is not real — the shipped default model cannot run
the shipped default loop.

**Independent Test**: Drive the task loop with a provider double that returns, in
order: unparsable text, an off-schema decision, a call to a tool that does not
exist, and finally a valid finish. The run completes and the trace records each
recovery.

**Acceptance Scenarios**:

1. **Given** a task loop and a model that returns text which is not valid JSON,
   **When** the step is evaluated, **Then** the run continues and the model is
   told, on the next step, that its previous output could not be read.
2. **Given** a model that names a tool which is not installed or not permitted,
   **When** the step is evaluated, **Then** the run continues and the model is
   told the name was rejected and which names are available.
3. **Given** a model that never produces a valid step, **When** the step budget
   is exhausted, **Then** the run ends with a `step_limit` status and a trace,
   not an exception.
4. **Given** a model that emits a reasoning preamble before its JSON,
   **When** the step is evaluated, **Then** the decision is still read correctly.

---

### User Story 2 - The Model Actually Gets Its Context Window (Priority: P1)

The same developer configures the context window they want and gets it, without
hand-writing a Modelfile or restarting the Ollama server with environment
variables.

**Why this priority**: Every other mitigation is undone by a 4096-token window.
This is invisible to the user today — nothing reports the effective size.

**Independent Test**: Configure a context window, start a task, and confirm the
model serving the request is loaded at that window rather than the server default.

**Acceptance Scenarios**:

1. **Given** a configured context window and a reachable Ollama, **When** a task
   runs, **Then** the model serves the request at the configured window.
2. **Given** the same configuration on a second run, **When** a task runs,
   **Then** no redundant provisioning work is repeated.
3. **Given** no configured context window, **When** a task runs, **Then**
   behaviour is unchanged from before this feature.
4. **Given** a provider that is not Ollama, **When** a context window is
   configured, **Then** it is ignored rather than applied incorrectly.

---

### User Story 3 - Observations Stay Inside the Budget (Priority: P2)

A tool returns a large result. The task keeps working instead of overflowing the
window and degrading into nonsense.

**Why this priority**: Silent context overflow looks like a bad model rather than
a harness defect, which is exactly the diagnosis the reporting user made.

**Independent Test**: Register a tool returning far more text than the budget, run
a multi-step task, and assert the assembled prompt stays within the budget while
the most recent observations survive.

**Acceptance Scenarios**:

1. **Given** a tool result larger than the observation limit, **When** it is
   recorded, **Then** it is truncated to the limit with the truncation visible to
   the model.
2. **Given** more observations than the retained window, **When** the next step
   prompt is built, **Then** the most recent observations are kept and the older
   ones are summarised as omitted.
3. **Given** a small model configuration, **When** limits are not set explicitly,
   **Then** defaults suited to a 4B model apply rather than the previous
   20,000-character limit.

---

### User Story 4 - The Loop Does Not Spin (Priority: P3)

A small model repeats the same tool call every step. The harness notices and
pushes it towards an answer instead of burning the whole step budget.

**Why this priority**: Repetition is the most common small-model loop failure
after schema slips, and it wastes the budget that recovery depends on.

**Independent Test**: Return the same tool call for every step and assert the
model is told the call was already made and its earlier result reused.

**Acceptance Scenarios**:

1. **Given** a tool call identical to one already made in this run, **When** the
   step is evaluated, **Then** the tool is not re-invoked and the model is told
   the prior result stands.

---

### Edge Cases

- The model returns a step whose `action` is `tool` with no tool named: rejected
  in-band so the model spends a model retry naming one, rather than a step. An
  answer offered alongside it is not accepted, because a model that chose a tool
  and answered anyway has answered without evidence.
- The model finishes without ever trying an available tool: pushed back once, so
  a small model answering from its priors gets one chance to reach for the tool.
  A tool that was called and failed counts as tried, so the push-back never aims
  the model at a tool that cannot work.
- A tool handler raises: recorded as a failed observation, run continues.
- A tool is marked destructive: still refused, and the refusal is reported to the
  model as an observation rather than raising.
- Ollama is unreachable while a context window is configured: the run falls back
  to the deterministic local provider as before; provisioning failure never
  becomes a task failure.
- The configured model tag already carries a matching context parameter: no
  provisioning is attempted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The task loop MUST treat an unreadable or off-schema model decision
  as a recoverable step, feeding the failure back to the model, until the step
  budget is exhausted.
- **FR-002**: The task loop MUST treat an unknown, unpermitted, or destructive
  tool name as a recoverable step and MUST tell the model which tool names are
  available.
- **FR-003**: The task loop MUST treat an exception raised by a tool handler as a
  recoverable observation.
- **FR-004**: A task run MUST NOT raise on model or tool misbehaviour; it MUST end
  with a status and a trace.
- **FR-005**: Structured decisions MUST be requested from the model as a
  constrained output using the model framework's own structured-output and retry
  mechanisms, not as a schema pasted into the prompt.
- **FR-006**: Reasoning preamble emitted before or around a JSON decision MUST NOT
  prevent the decision from being read.
- **FR-007**: Users MUST be able to configure a context window per provider, and
  the system MUST make the local model serve requests at that window.
- **FR-008**: Context-window provisioning MUST be idempotent and MUST apply only
  to local Ollama providers.
- **FR-009**: Provisioning failure MUST degrade to unprovisioned operation with a
  reported reason, never to a failed task.
- **FR-010**: Observations MUST be truncated to a configurable per-observation
  character limit whose default suits a 4B model.
- **FR-011**: The step prompt MUST retain only a configurable number of the most
  recent observations and MUST state that older ones were omitted.
- **FR-012**: Repeated identical tool calls within a run MUST NOT re-invoke the
  tool and MUST be reported back to the model as already answered.
- **FR-013**: Status output MUST report the effective context window and whether
  provisioning succeeded, so the user can see the number the model is running at.
- **FR-014**: All new limits MUST be configuration with defaults; no new required
  configuration may be introduced.
- **FR-015**: A decision the loop cannot act on MUST be rejected during output
  validation, so the correction costs a model retry rather than a task step.
- **FR-016**: A finish that never attempted an available tool MUST be pushed back
  a bounded number of times, and MUST NOT be pushed back for a tool that already
  produced a successful observation.
- **FR-017**: The step instructions MUST state that every fact in an answer comes
  from the observations, because a small model otherwise answers from its priors.
- **FR-018**: A provider whose configured model is not installed locally MUST
  report itself unavailable, with a reason naming the command that installs it.
- **FR-019**: Repeated provider-level failure MUST end the run with the provider's
  own error, rather than consuming the step budget and reporting a step limit.
- **FR-020**: A repeated identical tool call MUST be detected regardless of how
  the first call ended. A call that failed or was rejected is still a repeat, and
  re-running it consumes the budget that recovery depends on.
- **FR-021**: The toolless-finish push-back MUST consider a tool attempted once it
  has been called, whether or not it succeeded; the model must not be pushed back
  towards a tool that already raised.
- **FR-022**: A tool that has failed a configurable number of times MUST NOT be
  invoked again in that run. Matching repeats on arguments alone is insufficient,
  because a model that varies its arguments on each retry bypasses it.

### Key Entities

- **Task step decision**: the model's per-step choice — an action, a reason, an
  optional tool and arguments, an optional answer.
- **Observation**: the recorded outcome of one step, bounded in size, carrying
  whether it succeeded, failed, or was rejected.
- **Provider context profile**: the configured window for a provider plus the
  effective window actually in force and how it was obtained.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A task run survives at least three consecutive malformed model
  decisions and still completes when the model recovers.
- **SC-002**: No model or tool misbehaviour produces an uncaught exception from a
  task run; every failure path returns a result with a trace.
- **SC-003**: With a context window configured, the local model serves requests at
  that window rather than the 4096-token server default.
- **SC-004**: The step prompt for a run with ten large tool results stays within
  the configured observation budget.
- **SC-005**: Default limits are chosen so a 4B model with an 8k window has room
  for the instruction, the tool list, and the retained observations.
- **SC-006**: The existing test suite continues to pass unchanged.
- **SC-008**: A user who has configured a model they have not pulled learns that
  from the first run and from `atbots status`, not after a full step budget of
  silent failures.
- **SC-007**: A 1.7B model — a harder case than the reference `qwen3:4b` —
  completes a two-step tool loop against the real server and answers from the
  tool result rather than from its priors.

## Assumptions

- The target is a 4B-class instruct model with reasoning output, served by Ollama
  on the user's own machine; `qwen3:4b` is the reference case.
- The local server exposes both an OpenAI-compatible surface and a native surface;
  the OpenAI-compatible surface remains the inference path.
- Recovery is bounded by the existing step budget; no new unbounded retry loop is
  introduced.
- Skill instruction injection remains out of scope, as recorded in the
  general-purpose-agent specification.
