# 006 — User-owned AtBots agent platform

Date: 2026-10-26. Status: implementation in progress; not released.
Feature directory: `specs/006-agent-control-room`; its name does not limit scope.
Governing constitution: 4.0.0. Authentication dependency: feature 005.

## Outcome and scope

Install AtBots and manage persistent personal agents through conversation:
create, configure, assign work, schedule, supervise, inspect, deploy, move,
pause and retire. Use the same operations from terminal, library and optional
web control room. AtMem is default memory, AtFlows is optional observability
and AtSys is optional supervised worker/observer/supervisor execution.
An agent's model and the models for AtSys roles are independently configurable.
Consume AtSys 0.3.0b4's Codex, Claude Code and GitHub Copilot CLI adapters;
catalog detection alone is not sufficient runtime acceptance.

This is the full agent platform, not just a dashboard, chatbot or script
wrapper. No AtBots-hosted service is required. Deployment, scheduling, browser
work, skills, workspace tools, integrations and supervision are in scope.
Optional means an individual agent need not enable them; it does not mean the
implementation may omit them. Model/tool execution remains Pydantic AI's job.

## User journeys and acceptance

### US1 — Create, configure and reopen agents (P1)

Run `atbots` and say "Create a researcher using my local model", or use
`atbots --new researcher`. Configure instructions, model, workspace and permissions
by conversation. Reopen it using `atbots researcher`. Reserved management names
cannot be agent names. Invalid names and paths fail before any filesystem change.

Acceptance: two agents created in a temporary root have distinct IDs, histories,
memory scopes and browser profiles; configuration survives restart. Creation
alone causes no model download, paid request, browser launch or cloud provisioning.
Legacy configuration import is explicit and does not overwrite the source.

### US2 — Converse with the fleet and with individual agents (P1)

"Ask researcher what it found", "What is the supervisor doing?", "Use model X
for developer", "Pause that task" and "Show me the report" resolve into bounded
typed operations. The user can enter an agent's conversation or address it from
the control room. Every answer names its speaker and target. Asking questions
does not cancel ongoing work. Ambiguous recipients require clarification.

Acceptance: management requests and direct chat reach the intended recipient;
changes pass validation/policy; status comes from job events and includes last
update time. An unreachable runner is reported stale/unreachable, not running.
Completion displays deliverables and verification, not just a success badge.

### US3 — Inspectable AtMem memory (P1)

Recall applicable memories before relevant work; capture policy-eligible user
facts and lessons afterward. Support remember, search, inspect, correct and
forget through chat. Show sources, lifecycle and scope. Sharing is explicit.

Acceptance: capture and recall use the port and AtMem authority APIs; secrets
are filtered; failed capture is never claimed saved; unrelated agent memories
are absent. Unverified agent output remains an attributed observation, not a
verified lesson. Revocation stops future sharing but cannot erase prior exposure.

### US4 — Browser, workspace and skills (P1)

An agent browses permitted sites, works with approved files and produces
artifacts. The user can watch, log in and take over the browser. Agent profiles
are separate by default. Missing capabilities can lead to a proposed skill.

Acceptance: real upstream tools demonstrate navigation, screenshots, click/type
and handoff on a local fixture site. Unapproved domains/actions are refused.
MFA/CAPTCHA pauses for the user. Page instructions cannot grant capabilities.
File traversal/symlink escapes are refused. Executable skill installation needs
source/dependency review and approval. Browser-only unattended X automation is
not advertised as compliant with X's automation policy.

### US5 — Reliable schedules and background work (P1)

"Every Monday at 9 Sydney time", "Once tomorrow", "Skip missed runs" and
"Don't overlap these" become durable schedules. Preview next occurrences and
edit/pause/delete conversationally. Work does not depend on an open chat window.

Acceptance: clock-based tests cover restart, duplicate triggers, timezone/DST,
overlap and missed runs. Local schedules explain runner availability requirements.
Ambiguous times are clarified. A crash after an uncertain consequential action
does not trigger blind replay. No exactly-once external-effect claim is made.

### US6 — AtFlows observability and AtSys supervision (P1)

"Show this agent's model usage" uses the optional AtFlows integration. AtFlows
supplies model-call tracing, tokens, latency and available cost telemetry; it is
not a workflow execution engine. "Implement and test this under supervision"
delegates an objective to AtSys with acceptance criteria, deadlines, resource
limits and role-specific providers/models, without competing recovery authority.

Acceptance: real supported interfaces provide upstream run IDs and status.
Missing integration gives actionable setup instructions, not fake delegation.
Fault injection demonstrates worker execution, observer detection, supervisor
intervention and a verified output. Actual role-model provenance matches config.
Questions, amendments and cancellation reach the execution owner.

AtSys 0.3.0b4 already implements Codex, Claude Code and GitHub Copilot CLI
adapters. Worker runtime/model and supervisor runtime/model are distinct
bindings; observer runtime/model applies when a model-based observer is enabled.
Deterministic observers/validators remain available without a model. Native
noninteractive execution, structured proposal validation, process cancellation,
bounded recovery and honest capability reporting are required. Cross-runtime
supervision is supported only when the configured permission boundary can be
enforced; a read-only instruction alone is not a read-only sandbox.

### US7 — Deploy and operate an agent through chat (P1)

"Deploy researcher cheaply on Cloud Run", "What will it cost?", "Show remote
logs", "Stop deployment" and "Move it back to my Mac" use the same validated
operations as explicit CLI commands. Deployment is implemented, not just described.

Acceptance: build a pinned container, inspect a deployment plan, grant permission
and budget, provision secrets explicitly, run a harmless scheduled cloud job,
retrieve its artifact and stop/remove resources. State survives restart. Moving
an agent fences the old runner before activating the destination. No credentials
are bundled in portable definitions. Mocked cloud tests alone do not prove this.

### US8 — Web control room (P2)

Chat, inspect memories/agents/artifacts, watch progress, approve actions and
configure deployment in a browser, using the terminal's management service.
Local access is default; remote access needs authenticated protected transport.

Acceptance: browser tests exercise chat-based create/configure/work/status,
approval, memory inspection, artifacts and error recovery. Unauthorized access,
cross-agent access and CSRF are rejected. Credentials/debugging ports stay private.

## Functional requirements

### Lifecycle and conversations

- FR-001: Provide interactive `atbots`, `--new NAME`, named-agent chat and explicit
  management commands while preserving feature-005 authentication commands.
- FR-002: Persist versioned definitions: stable ID, name, provider/model,
  instructions, workspace, memory scope and grants. Validate before applying.
- FR-003: Isolate histories, files, browser state and memory. Make sharing explicit,
  revocable and auditable; do not call directory scoping a code-execution sandbox.
- FR-004: Support list/inspect/configure/pause/resume/retire, with explicit
  retention/export choices before destructive retirement.
- FR-005: Use native Pydantic AI Agent/toolsets/message history; expose the Agent
  and accept native models/tools. Do not add another model/tool execution loop.
- FR-006: Preserve local default, explicit remote access and feature-005 consent,
  entitlement, credential-store and unavailable-provider behavior.
- FR-007: Translate plain English into schema-validated management operations
  with target/operation IDs; never run unrestricted generated shell commands.
- FR-008: Distinguish questions, instructions, config changes and cancellation;
  clarify ambiguous targets and display the speaker on every answer.
- FR-009: Persist conversations and support questions while work runs. Task
  amendments are versioned and acknowledged by the execution owner.
- FR-010: Show authoritative state, heartbeat freshness, interventions, blockers,
  approvals, outputs and verification; unknown/stale is not running/completed.
- FR-011: Bind approvals to operation/parameters/target/expiry. Invalidate stale
  approvals; support narrow reusable grants and revocation.
- FR-012: Enforce request/token/time limits and infrastructure spending grants.
  Unknown prices must not be presented as an enforceable dollar cap.

### Memory and capabilities

- FR-013: Default to an AtMem memory port preserving provenance, admission,
  applicable recall, lifecycle, secret filtering and exposure controls.
- FR-014: Expose memory search/inspect/correct/forget/sharing through chat and
  explicit operations; enforce authorization below the model-prompt layer.
- FR-015: Distinguish statements, observations and verified outcomes; do not dump
  unfiltered browser traces into memory or promote output to verified truth.
- FR-016: Provide approved-root file tools and upstream browser tools with domain/
  action permissions, session locking and safe download handling.
- FR-017: Preserve native image/tool payloads for vision models; report capability
  mismatch rather than stringify screenshots into the legacy text-only loop.
- FR-018: Discover skills and load relevant instructions on demand; installation
  pins source/version and reviews code, dependencies and requested permissions.
- FR-019: Support browser takeover and explicit encrypted session provisioning;
  no credential scraping, MFA/CAPTCHA bypass or target-site policy evasion.

### Durable execution and integrations

- FR-020: Persist jobs/events/checkpoints with validated transitions, correlation/
  idempotency IDs, deadlines, cancellation and bounded recovery.
- FR-021: Assign one execution owner to each unit: AtBot or AtSys objective.
  AtFlows observes rather than owns execution. Persist upstream IDs and never
  duplicate recovery authority.
- FR-022: Support durable one-shot/recurring schedules, IANA timezones, DST,
  overlap/missed-run policies and next-occurrence preview.
- FR-023: Use leases/fencing and side-effect receipts to prevent avoidable double
  execution; uncertain consequential outcomes require reconciliation/handoff.
- FR-024: Implement optional AtFlows model-call observability using supported
  proxy/telemetry contracts, retaining model authentication, egress and provenance.
  Do not route subscription OAuth through an unsupported compatible proxy. Trace
  absence and unknown cost remain explicit; AtFlows does not execute workflows.
- FR-025: Implement optional version-checked AtSys submit/status/question/amend/
  cancel/result with real worker/observer/supervisor provenance.
- FR-026: Configure AtSys role models, secret references, acceptance criteria,
  escalation, deadlines and resource limits through validated operations.
- FR-027: Give actionable missing-dependency/grant/resource errors; never silently
  substitute a different model or execution owner.

### Deployment and operations

- FR-028: Package portable manifests and a pinned container runtime; exclude
  tokens, raw private histories and unrestricted browser profiles from exports.
- FR-029: Implement local and Cloud Run Jobs runners, external persistent state,
  single-writer ownership and cloud-native secret provisioning.
- FR-030: Provide chat/CLI deployment plan/apply/status/logs/stop/destroy, including
  cost assumptions, region, image digest and resource ownership receipts.
- FR-031: Keep state outside ephemeral container files. Checkpoint SQLite safely
  or use an appropriate transactional store; do not treat object storage as a
  concurrently writable SQLite filesystem.
- FR-032: Support export/import/move with quiescence, revision checks, secret
  re-provisioning and destination validation; no arbitrary live-browser migration
  or unsupported memory-format migration promise.
- FR-033: Implement a first-party authenticated web client using the same
  operations/events; local bind by default, protected remote mode.
- FR-034: Provide doctor/preflight for model, memory, skills, browser, scheduler,
  AtFlows/AtSys, cloud permissions and budget configuration.
- FR-035: Provide redacted logs/events, retention/export and accessible artifacts;
  absent receipts and stale heartbeats are visible failures, not silent success.
- FR-036: Preserve library/auth behavior. Document exact companion/CLI replacements
  and compatibility effects before removal; no silently removed capabilities.
- FR-037: Deliver pip extras, installed-wheel tests, macOS/Windows/Linux checks
  and guides. Implementation alone does not authorize publication or billable
  cloud provisioning without a specific applicable spending grant.

### Multi-runtime AtSys dependency

- FR-038: Consume AtSys >=0.3.0b4 with genuine Codex, Claude Code and GitHub
  Copilot CLI adapters; canonical provider IDs are codex, claude and copilot.
  Reuse its invocation, role selection, normalization and cancellation rather
  than implement another supervision engine. Verify the installed interface.
- FR-039: Configure runtime and model independently for worker and supervisor
  and, when enabled, model-based observer. Apply deterministic authority and
  declared validators independently of runtime. Unsupported diagnosis/repair/
  sandbox/network/session capabilities fail closed or use an explicitly chosen
  supported role runtime; never silently fall back to Codex or bypass permissions.
- FR-040: Validate each adapter with hermetic contract/fault tests and separate
  harmless live acceptance where installed/authenticated. Cover worker success,
  validator failure, bounded supervisor proposal, policy-authorized recovery,
  cancellation, unavailable CLI and malformed output. Record tested CLI versions
  and missing telemetry; native resume, usage and hook parity must not be inferred.

## Entities and ownership

AgentDefinition contains model/resource/secret references, not token values.
Conversation stores native history and speaker identity. Job has one owner,
Attempts and Deliverables. Approval binds a proposed operation. Schedule creates
jobs; it is not another agent loop. Deployment records resource identity and
runner lease. Memory belongs to its backend; job state belongs to its execution
owner. AtSys operational records remain authoritative for AtSys work.

The control room questions agents/supervisors out of band. It can summarize
recorded decisions but cannot fabricate live answers or demand hidden chain of
thought. Store observable actions/results, not private reasoning transcripts.

## Success criteria / evidence gates

- SC-001: Clean-install tests show create/reopen/two-agent isolation, library/CLI
  execution and feature-005 regression coverage.
- SC-002: A versioned intent evaluation set covers each operation family,
  paraphrases, ambiguous targets, revoked grants and malicious page text. Zero
  unauthorized mutations in deterministic fixtures; live-model routing quality
  is measured separately, never asserted universally safe from scripted tests.
- SC-003: Real AtMem tests cover capture/recall/correction/forget and cross-scope
  denial; interface tests show a substitute backend without objective rewrites.
- SC-004: Local fixture-site acceptance uses real browser tools for navigation,
  screenshot/vision payloads, form interaction, approval and takeover.
- SC-005: Clock/fault tests cover schedules, restart, stale lease, cancellation,
  duplicate triggers and uncertainty without blind irreversible replay.
- SC-006: Real integration acceptance records a model call in AtFlows and runs
  an AtSys objective with injected recoverable failure and visible intervention.
- SC-007: Cloud acceptance records deploy/run/artifact/restart/cleanup, exact
  resource/image IDs and measured charges, separate from mocked API tests.
- SC-008: Terminal/web walkthroughs create/configure/work/status/approve/access
  results without undocumented commands; screenshots verify readable identity,
  progress and discoverable deliverables.
- SC-009: Build/installed-artifact and platform gates pass; unavailable hosts,
  credentials or provisioning grants are named external blockers, not hidden
  behind an overall complete checkbox.
- SC-010: AtSys multi-runtime acceptance reports a per-runtime/role matrix for
  Codex, Claude Code and GitHub Copilot CLI, plus at least one explicitly
  configured mixed-runtime supervised job. Unsupported cells and untested
  operating systems remain visible. Adapter capability detection is verified
  against actual invocation behavior, not executable presence alone.

Local, integration, cloud and publication readiness are separate. No product-
complete claim until all in-scope gates have evidence or scope is explicitly
revised by the owner. See [platform-boundaries.md](platform-boundaries.md) for
architecture constraints, ordered delivery slices and compatibility decisions.
