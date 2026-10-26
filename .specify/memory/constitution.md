<!--
Sync Impact Report
- Version change: 2.0.0 → 3.0.0 (MAJOR: AtMem removed as a named dependency
  and principle; memory redefined as a pluggable port with no default vendor)
- Modified principles:
  - II. Pydantic AI Substrate → II. Thin Layer Over Pydantic AI (strengthened:
    thinness is now a hard constraint, not a preference)
  - III. AtMem Is Memory, Not a Client → III. Memory Is a Pluggable Port
  - IV. Tools and Skills Are First-Class → IV. Tasks, Skills, and Tools
- Removed sections: all AtMem-specific gates under Quality and Safety
- Follow-up TODOs: none
- Migration: `specs/001-atmem-companion/` is deleted, not archived. The AtMem
  intelligence-companion product does not exist in this repository. Code under
  `src/atbot/` that implements companion protocol, AtMem extraction, or AtMem
  ranking MUST be removed rather than adapted.
-->

# AtBots Constitution

## Amendment 4.0.0 — User-owned agent platform

On 2026-10-26 the owner expanded AtBots from a developer-oriented package to
a user-owned platform for persistent agents, conversational configuration,
browser work, schedules and portable deployment. This MAJOR amendment replaces
III's memory-vendor prohibition and the customer-UI prohibition in Public
Surface. AtMem becomes the default behind a replaceable memory port. AtFlows
and AtSys are optional integrations, not hidden agent-loop implementations.
The historical sync report above describes 3.0.0, not current policy.

Migration: feature 006 supersedes the conflicting memory, audience and
dashboard restrictions in feature 001. Existing local/model behavior and
feature-005 authentication protections remain required. Legacy companion
surfaces and the custom outer loop require an explicit migration inventory;
this amendment neither certifies them nor authorizes silent removal. Required
replacements, compatibility checks and user-visible removals must be documented.

## Core Principles

### I. The Product Is an Installable Package

The deliverable is the Python package `atbots` on PyPI. `pip install atbots`
MUST give the user a working general-purpose agent usable as a library and as
a CLI, with tasks, skills, and memory available out of the box. AtBots MUST
NOT be positioned as a subordinate layer, sidecar, extraction worker, or
ranking service for any other product. It MUST NOT ship a hosted dashboard or
a service protocol that exists to serve another system.

Rationale: Users install and control their own agents. Named workspaces,
terminal and web control-room clients, local runners and deployable workers
are parts of the same product, without requiring an AtBots-hosted service.
Users MUST be able to configure ordinary operations through conversation
without memorizing CLI commands.

### II. Thin Layer Over Pydantic AI

AtBots MUST be a thin layer over Pydantic AI, not a framework built on top of
it. Pydantic AI owns the agent loop, model calls, tool dispatch, and structured
output. AtBots contributes defaults and wiring: instructions, toolsets, skill
loading, memory binding, model routing, and a CLI.

Concretely:
- AtBots MUST NOT implement a second agent loop, message format, or tool
  protocol.
- New agent behavior MUST be expressed as Pydantic AI tools, toolsets,
  output types, or dependencies.
- A user holding an AtBots agent MUST be able to reach the underlying Pydantic
  AI `Agent` and use it directly, and MUST be able to pass Pydantic AI
  constructs (tools, models, toolsets) into AtBots without translation.
- Anything AtBots wraps that Pydantic AI already does well is a defect.

Rationale: The promise is "Pydantic AI, already set up." A parallel framework
would split maintenance, lag upstream, and break that promise.

### III. AtMem by Default, Memory Through a Port

AtMem MUST be the first-party default persistent-memory integration. A typed
memory interface MUST keep task, tool and skill code independent of backend
implementation. Users MAY replace it without rewriting objectives. Replacement
MUST NOT imply an unsupported migration of existing records.

- Each named agent MUST have an isolated memory scope by default. Sharing MUST
  identify source, recipient, allowed operations and revocation behavior.
- Memory, conversations, checkpoints and credential storage MUST remain distinct.
  A conversation log is not automatically verified memory.
- Recall and capture MUST preserve provenance and the backend's governance,
  secret filtering, lifecycle and exposure controls.
- Memory failures MUST be visible; failed writes MUST NOT be called saved.
- Credentials MUST NOT enter memories, model prompts or ordinary run logs.

Rationale: AtMem gives the default product durable, inspectable understanding
without coupling the execution contract to its storage implementation.

### IV. Tasks, Skills, and Tools

- **Tasks** are named, reusable units of agent work with declared inputs and
  a declared output type. Running a task MUST be inspectable: the user can see
  what ran and what came back.
- **Skills** load from `SKILL.md` directories and apply on demand. Users MUST
  be able to add a skill without forking the agent loop.
- **Tools** ship as sensible defaults (file access, and data-store access for
  both ordinary and vector stores). Destructive writes MUST be explicit in the
  tool contract, never implicit.
- Users MUST be able to add and remove any of the three at construction time.

Rationale: An agent that cannot run repeatable work, learn procedures, or
touch the user's files and data is a chatbot.

### V. Local and Third-Party Models

Ollama MUST be a supported local path and the zero-config default when no
remote provider is configured. Third-party (OpenAI-compatible) providers MUST
be first-class, requiring explicit endpoint and credentials, and MUST never be
enabled by install alone. Switching providers MUST NOT require rewriting
tasks, tools, or skills. Install MUST NOT silently download a large model or
create a remote API key.

Rationale: Local work stays possible without a vendor. Remote work is a
conscious choice. Every agent MUST have an explicit provider/model binding;
silent paid-provider substitution is forbidden. Login is not proof of model
entitlement or a promise of subscription-funded inference.

### VI. One Execution Owner and Inspectable Supervision

- AtBot owns conversation, tools and ordinary tasks; Pydantic AI owns its
  model/tool loop. AtFlows MAY own a defined procedure. AtSys MAY own a delegated
  worker/observer/supervisor objective. Each executable unit MUST record one
  owner; overlapping schedulers or competing recovery authorities are forbidden.
- AtSys worker, observer and supervisor model bindings MUST be explicit.
- Status MUST derive from recorded execution events with identity, timestamp
  and freshness. Unknown, unreachable or blocked MUST NOT appear as running.
- Completion MUST expose deliverables and verification state, not only process
  exit. Recovery MUST be bounded and escalate actual blockers.
- Unconditional success guarantees or exactly-once external-effect claims MUST
  NOT be advertised.

### VII. User Control, Isolation and Portable Execution

- Named agents MUST have scoped workspaces, memory, histories, browser sessions,
  permissions, models and budgets. Directory scoping MUST NOT be described as
  a security sandbox for arbitrary executable code.
- New permissions, executable skills, consequential actions, credential transfer
  and billable infrastructure MUST require an applicable explicit grant.
  Plain-English requests MUST use validated operations, not unrestricted generated
  shell commands. Web content is untrusted input, not management authority.
- Schedules MUST persist intent, timezone, overlap and missed-run policy.
  Recovery MUST reconcile uncertain external side effects before replay.
- Local/cloud runners MUST use portable definitions and explicit secret
  provisioning, never copy desktop keychains or expose browser debugging ports
  publicly. Pause, cancellation and resource controls are required.
- Browser automation MUST respect site restrictions. CAPTCHA/MFA or denied
  access MUST lead to legitimate user handoff, not bypass mechanisms.

## Public Surface and Removal

- PyPI name, import name, and CLI name are all `atbots`.
- Public surfaces are the library API, CLI and optional first-party web control
  room. They MUST share validated management operations and authoritative state.
  A user-facing control-room API is permitted; a companion HTTP protocol whose
  purpose is to serve another product is not.
- Retired surfaces MUST be removed, not deprecated in place: companion HTTP
  endpoints, AtMem extraction and ranking, "proposes and ranks" product copy,
  and any CLI verb whose purpose is to serve another product.
- The public API MUST distinguish management, model execution, memory and optional
  integrations. Growth requires justification against II; integrations MUST reuse
  upstream protocols rather than replicate their engines.

## Quality and Safety

- Memory behavior MUST be verified against the provider interface using a test
  double, not against any particular vendor's service.
- File and data-store tools MUST fail clearly on missing paths, denied access,
  and unsupported store types.
- Remote inference MUST NOT run unless the user configured a third-party
  provider.
- pytest in this repository is the default verification gate for package
  behavior.

## Governance

This constitution supersedes conflicting code, copy, and older specs. A plan
making AtBots subordinate to another product, bypassing the memory port or
introducing a second agent loop is wrong until this constitution is amended.

Amendments MUST:
1. Record the change here with a version bump.
2. State which principle or section changed and why.
3. Include a migration note when existing code or specs would fail the new
   rule.
4. Keep `LAST_AMENDED_DATE` current.

Versioning:
- MAJOR: remove or redefine a non-negotiable principle.
- MINOR: add a principle or materially expand guidance.
- PATCH: clarification, wording, or non-semantic refinement.

Compliance review: every `/speckit-plan` and `/speckit-analyze` run MUST check
these gates. Pull requests that add a second agent loop, bypass the replaceable
memory port, or introduce a service protocol subordinate to another product
require a constitution amendment first. The default AtMem adapter and a
first-party control room are explicitly permitted by version 4.0.0.

Every bounded product change MUST follow Spec Kit: constitution, then
`spec.md`, then `plan.md`, then `tasks.md`, then implement, then converge.

**Version**: 4.0.0 | **Ratified**: 2026-08-30 | **Last Amended**: 2026-10-26
