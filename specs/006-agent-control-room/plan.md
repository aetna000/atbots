# Implementation plan — full AtBots platform

## Context and constitution check

Python >=3.11, Pydantic 2, Pydantic AI >=2.61 (verified native auth floor), SQLite
and filelock. Reuse feature 005 provider/credential code. Add native execution
alongside the legacy TaskAgent without silently rewriting its semantics. New
platform sessions expose a Pydantic AI Agent and pass native models/tools/toolsets.
Native Pydantic AI owns the loop; SQLite owns identity/config/history/revisions.
AtMem remains first-party memory behind a port. AtSys is optional supervision;
AtFlows is optional tracing, not a workflow engine. Constitution III/VI permit
these boundaries. No duplicate supervisor, model transport or hosted requirement.

Preserve the dirty evals/baseline.json and all feature-005 work. No commit/release
or paid deployment in this implementation pass. Legacy companion removal is a
separate explicit migration task; existing tests remain meaningful, not proof of
new native-loop quality. Do not invoke optional Git auto-commit hooks.

## Components and files

- `platform/models.py`: strict portable agent definition, provider and limits.
- `platform/store.py`: private named workspaces and SQLite definitions/conversations,
  compare-and-swap revisions and atomic turn ownership. No secret values in config.
- `platform/session.py`: model construction via existing providers, real native
  Agent, history, scoped memory tools, limits and explicit error/usage receipts.
- `platform/control.py`: native structured intent parsing into bounded operations,
  clarification/approval and deterministic dispatch. No generated shell execution.
- `platform/cli.py`: create/list/inspect/configure/chat/control-room; root `cli.py`
  routes additively and retains existing auth/init/status/doctor/serve commands.
- `platform/memory.py`: memory port and AtMem adapter, context/exposure receipts,
  explicit capture and scoped inspect/correct/forget; sharing is refused. Keep secrets out of model history.
- `platform/connections.py`: reusable native account/API references, OS keychain,
  bounded provider catalogs and browser sign-in without an inference dependency.
- `platform/environment.py`: own-workspace/memory identity, scoped tools and
  operator-approved supervision/schedule proposals; built-in AtSys skill.
- `platform/desktop.py`: private authenticated background UI and one runner per
  root, no idle inference, reconnection without duplicate ownership.
- `platform/components.py`: real installed versions and confirmed compatible
  package maintenance, quiescence checks and restart-required state.
- `platform/supervision_service.py`: explicit private AtSys startup through its
  installed CLI, agent-owned state, verified instance/watchdog identity and
  opt-in workspace Git initialization without global configuration changes.
- Later files: `jobs.py`, `scheduler.py`, `browser.py`, `skills.py`, integration
  adapters, cloud runner/container and first-party web service/client.

SQLite stays local to the store; one serialized turn per conversation prevents
lost updates. Stable UUIDs determine paths and scope; names are validated aliases,
not raw path fragments. Provider secrets are references only. Config validation
rejects credential-like fields; no raw CLI errors or secret output to prompts.
History is private native-message JSON, separate from persistent memory and logs.
Retention/export and semantic secret filtering require their explicit later gates;
do not describe the initial history store as a complete DLP system.

## Integrations and acceptance

AtSys >=0.3.0b4 uses worker IDs codex/claude/copilot, supervisorProvider and
repairProvider with model/effort bindings and trustedLocalExecution where needed.
Use supported task submit/status/action/report APIs; independent evidence remains
AtSys-owned. Out-of-band questions may use recorded state; do not invent a native
live steering/question endpoint. Model-based observer support is feature-detected.
AtFlows uses its supported compatible-provider proxy recipe or telemetry exporter;
subscription-native endpoints are not silently redirected through it.

Cloud target: Cloud Run Jobs with pinned image, external transactional state and
explicit cloud secrets/leases. Local SQLite files cannot be concurrently edited
through an object-store mount. Deployment grants must precede actual provisioning.

Tests: deterministic fake native models, real temporary SQLite/AtMem, mocked HTTP
for transport; opt-in local model/browser/AtSys/AtFlows and paid cloud acceptance
are reported independently. Python 3.12 macOS initially; Windows/Linux validation
needs its own evidence. Build/install artifacts as well as source tests.

## Delivery order and completion rule

Owner correction (2026-10-27) prioritizes T019–T022 below over older open feature
extensions: strict memory walls and truthful native capabilities, then reusable
provider setup and guided UI/model switching, then user-journey verification.
Prior sharing behavior is superseded; preserve records but reject new sharing
and ignore existing sharing edges during recall. Do not retrofit credentials or
enable file/cloud permissions on existing agents without the operator's choice.
Control-room planning receives configuration/status metadata only. Per-agent
memory inspection is an operator/agent view, not control-room model context.

T001 contracts/store; T002 native session/model wiring; T003 CLI/structured control;
T004 full memory integration; T005 durable jobs/approvals; T006 browser/files/skills;
T007 scheduler; T008 AtSys/AtFlows; T009 cloud portability; T010 web; T011 acceptance,
docs and convergence. All slices remain scope. Mark individual tasks complete only
with their evidence; a runnable foundation is not whole-platform completion.
