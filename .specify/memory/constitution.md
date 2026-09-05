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

## Core Principles

### I. The Product Is an Installable Package

The deliverable is the Python package `atbots` on PyPI. `pip install atbots`
MUST give the user a working general-purpose agent usable as a library and as
a CLI, with tasks, skills, and memory available out of the box. AtBots MUST
NOT be positioned as a subordinate layer, sidecar, extraction worker, or
ranking service for any other product. It MUST NOT ship a hosted dashboard or
a service protocol that exists to serve another system.

Rationale: Users install an agent and build with it. Any framing in which
AtBots exists to serve another product inverts who the customer is.

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

### III. Memory Is a Pluggable Port

Memory MUST be defined as a provider interface (store, recall, and their
async equivalents) with no vendor named in the core package. Any backend that
satisfies the interface is equally supported: an in-process default, mem0,
AtMem, a vector store, or a user-written class.

- Core `atbots` MUST NOT depend on, import, or reference a specific
  third-party memory product.
- Backend integrations, if shipped at all, MUST be optional extras that fail
  with a clear installation message when the backend is absent.
- Switching backends MUST NOT require rewriting tasks, skills, or tools.
- Vendor-specific setup belongs in documentation, not in the core contract.

Rationale: Memory backends are a competitive, fast-moving field. Binding the
package to one makes AtBots that vendor's client instead of the user's agent.

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
conscious choice.

## Public Surface and Removal

- PyPI name, import name, and CLI name are all `atbots`.
- Public surfaces are the library API and the CLI. This repository MUST NOT
  ship a customer dashboard or a companion HTTP protocol.
- Retired surfaces MUST be removed, not deprecated in place: companion HTTP
  endpoints, AtMem extraction and ranking, "proposes and ranks" product copy,
  and any CLI verb whose purpose is to serve another product.
- The public API MUST be small enough to document on one page. Growth in
  surface area requires justification against Principle II.

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

This constitution supersedes conflicting code, copy, and older specs. If a
plan or task would make AtBots the intelligence layer of another product, or
would bind core memory to a named vendor, the plan is wrong until this file is
amended.

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
these gates. Pull requests that add a second agent loop, a vendor dependency
in core memory, or a service protocol for another product require a
constitution amendment first.

Every bounded product change MUST follow Spec Kit: constitution, then
`spec.md`, then `plan.md`, then `tasks.md`, then implement, then converge.

**Version**: 3.0.0 | **Ratified**: 2026-08-30 | **Last Amended**: 2026-09-05
