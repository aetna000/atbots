# Feature Specification: AtBots — General-Purpose Agent Package

**Feature Branch**: `001-general-purpose-agent`

**Created**: 2026-09-05

**Status**: Draft

**Input**: User description: "atbots is a Python package on PyPI. When a user installs it they get Pydantic AI, customised — with tasks, skills, and memory. It is a thin layer. Memory is one pluggable option among many (AtMem, mem0, or any other); nothing is necessarily linked to a single backend. AtBots is not the intelligence layer for any other product."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and Get a Working Agent (Priority: P1)

A Python developer runs `pip install atbots`, points it at a local Ollama model
or an OpenAI-compatible endpoint, and immediately has a general-purpose agent
they can call from code or from a terminal. They did not have to assemble
instructions, a toolset, a memory layer, or a CLI themselves.

**Why this priority**: This is the entire product promise. Without it there is
no package, only a library of parts.

**Independent Test**: Install the package into a clean environment, configure a
model, run one prompt through the library API and one through the CLI, and get
a coherent answer both ways.

**Acceptance Scenarios**:

1. **Given** a clean environment with `atbots` installed and Ollama running,
   **When** the user creates a default agent and runs a prompt,
   **Then** the agent answers using the local model with no further configuration.
2. **Given** the same environment, **When** the user runs the `atbots` CLI with
   a prompt, **Then** they get the same answer path without writing code.
3. **Given** no model provider is configured and no local runtime is reachable,
   **When** the user runs a prompt, **Then** the failure names what is missing
   and how to configure it, rather than failing deep inside a client library.
4. **Given** an agent, **When** the user asks for the underlying Pydantic AI
   `Agent`, **Then** they receive it and can use every upstream feature directly.

---

### User Story 2 - Run Named, Repeatable Tasks (Priority: P1)

A developer defines a task once — a name, its inputs, its instructions, and the
shape of its result — and then runs it repeatedly from code, from the CLI, or
from inside another task, getting typed results each time.

**Why this priority**: Tasks are what separate an agent package from a chat
wrapper. They are the unit users build on.

**Independent Test**: Define a task with a structured output type, run it twice
with different inputs, and assert the results validate against the declared type.

**Acceptance Scenarios**:

1. **Given** a registered task with declared inputs and output type,
   **When** the user runs it with valid inputs,
   **Then** they receive a result validated against the declared output type.
2. **Given** the same task, **When** the user runs it with missing or wrongly
   typed inputs, **Then** it fails before any model call, naming the bad input.
3. **Given** a registered task, **When** the user lists tasks from the CLI,
   **Then** the task appears with its name, description, and expected inputs.
4. **Given** a completed task run, **When** the user inspects it,
   **Then** they can see the inputs, the tools called, and the final result.

---

### User Story 3 - Configure Any Memory Backend (Priority: P1)

A developer chooses where the agent's durable memory lives. Out of the box they
get a working local default with no third-party account. When they want a real
backend, they configure one — mem0, AtMem, a vector store, or their own class —
by satisfying the memory interface. Their tasks and skills do not change.

**Why this priority**: Memory is one of the three advertised pillars, and
vendor-neutrality is an explicit product constraint.

**Independent Test**: Run the same task against the default backend and against
a substitute backend implementing the interface; the task code is byte-identical
and both runs recall what was stored.

**Acceptance Scenarios**:

1. **Given** a fresh install with no memory configuration,
   **When** the agent stores and later recalls a fact,
   **Then** recall succeeds using the built-in default with no external service.
2. **Given** a user-supplied class implementing the memory interface,
   **When** it is passed to the agent, **Then** all stores and recalls route to
   it and no built-in backend is used.
3. **Given** a configured backend whose package is not installed,
   **When** the agent starts, **Then** it fails with a message naming the
   missing package and the command to install it.
4. **Given** a task written against one backend, **When** the backend is swapped,
   **Then** the task runs unchanged.
5. **Given** the core package, **When** its dependencies are inspected,
   **Then** no third-party memory product appears among them.

---

### User Story 4 - Load Skills on Demand (Priority: P2)

A developer drops a `SKILL.md` directory into a skills path. The agent discovers
it, and applies its instructions and bundled resources when the work calls for
it — without the developer editing the agent.

**Why this priority**: Skills make the agent extensible by writing documents
rather than code, but the package is already useful without them.

**Independent Test**: Place a skill directory in a configured path, run a prompt
in that skill's domain, and observe the skill's instructions taking effect.

**Acceptance Scenarios**:

1. **Given** a directory containing a valid `SKILL.md`,
   **When** the agent starts, **Then** the skill is discoverable by name and
   description.
2. **Given** a discovered skill, **When** a prompt falls in its domain,
   **Then** its instructions are applied to that run.
3. **Given** a malformed or unreadable skill directory,
   **When** the agent starts, **Then** it reports that skill as invalid and
   continues with the remaining skills.

---

### User Story 5 - Use Files and Data Stores (Priority: P2)

A developer gives the agent access to project files and to a data store —
either an ordinary relational/document store or a vector store — so it can
answer from the user's own material. Writes that destroy data are never implicit.

**Why this priority**: Default tools are what make the agent general-purpose
rather than a text box, but a user can supply their own tools in the interim.

**Independent Test**: Point the agent at a directory and a store, ask a question
answerable only from that content, and get a grounded answer.

**Acceptance Scenarios**:

1. **Given** a configured file path, **When** the agent is asked about its
   contents, **Then** it reads the files and answers from them.
2. **Given** a configured data store, **When** the agent is asked a question
   requiring it, **Then** it queries the store and answers from the result.
3. **Given** a request that would delete or overwrite data,
   **When** the agent attempts it, **Then** the destructive nature is explicit
   in the tool contract and the operation is refused unless enabled.
4. **Given** a missing path, denied permission, or unsupported store type,
   **When** a tool runs, **Then** it fails with a message naming the specific
   cause.

---

### User Story 6 - Switch Model Providers Without Rewrites (Priority: P3)

A developer prototypes against local Ollama and later moves to a hosted
OpenAI-compatible provider by changing configuration only.

**Why this priority**: Important for adoption, but the earlier stories deliver
value against a single provider.

**Independent Test**: Run the same task under a local provider and a remote
provider, changing configuration only.

**Acceptance Scenarios**:

1. **Given** no remote provider configured, **When** the agent runs,
   **Then** it uses the local model path and makes no outbound API call.
2. **Given** a configured remote endpoint and credentials, **When** the agent
   runs, **Then** it uses that provider and tasks, tools, and skills are unchanged.
3. **Given** installation alone, **When** nothing is configured,
   **Then** no large model is downloaded and no remote key is created.

---

### Edge Cases

- The configured model provider is unreachable mid-run — the failure must name
  the provider and the stage, not surface as an opaque client error.
- A memory backend errors on store or recall — the agent must report degraded
  memory rather than silently continuing as if the write succeeded.
- Two skills claim overlapping domains — both remain discoverable; selection is
  deterministic and inspectable.
- A task declares an output type the model cannot satisfy after retries — the
  run fails with the validation error, never with a coerced or partial result.
- A user passes a Pydantic AI tool or model object directly — it is accepted
  without an AtBots-specific wrapper.
- The skills path does not exist — the agent starts with zero skills and says so,
  rather than erroring.

## Requirements *(mandatory)*

### Functional Requirements

**Package and surface**

- **FR-001**: The distribution, import name, and CLI command MUST all be `atbots`.
- **FR-002**: Installing the package MUST provide a runnable agent as both a
  library API and a CLI, with no additional scaffolding by the user.
- **FR-003**: The package MUST expose the underlying Pydantic AI agent object to
  the user, and MUST accept Pydantic AI tools, toolsets, and model objects
  without translation.
- **FR-004**: The package MUST NOT implement its own agent loop, message format,
  or tool-dispatch protocol.
- **FR-005**: The package MUST NOT ship any HTTP protocol, dashboard, or CLI verb
  whose purpose is to serve another product.

**Tasks**

- **FR-006**: Users MUST be able to define a task with a name, description,
  declared inputs, and a declared output type.
- **FR-007**: The system MUST validate task inputs before any model call and
  reject invalid inputs with a message naming the offending field.
- **FR-008**: The system MUST validate task results against the declared output
  type and fail rather than return an unvalidated result.
- **FR-009**: Users MUST be able to list registered tasks and inspect a completed
  run's inputs, tool calls, and result.
- **FR-010**: Tasks MUST be runnable from the library API and from the CLI.

**Skills**

- **FR-011**: The system MUST discover skills from `SKILL.md` directories in
  configured skills paths.
- **FR-012**: The system MUST apply a skill's instructions and bundled resources
  on demand rather than loading all skills into every run.
- **FR-013**: An invalid skill MUST be reported and skipped without preventing
  startup or disabling other skills.

**Memory**

- **FR-014**: The system MUST define a memory provider interface covering store
  and recall, in both sync and async forms.
- **FR-015**: The core package MUST NOT depend on, import, or reference any
  specific third-party memory product.
- **FR-016**: The system MUST provide a working built-in default memory backend
  requiring no external service or account.
- **FR-017**: Users MUST be able to supply their own class implementing the
  interface, and have all memory operations route to it.
- **FR-018**: Any shipped backend integration MUST be an optional extra that,
  when its dependency is absent, fails with a message naming the missing package
  and its install command.
- **FR-019**: Swapping memory backends MUST require no change to task, skill, or
  tool code.
- **FR-020**: A memory backend failure MUST be surfaced as degraded memory, never
  silently swallowed.

**Tools**

- **FR-021**: The default agent MUST ship with file tools and data-store tools
  covering both non-vector and vector stores.
- **FR-022**: Destructive file or data-store operations MUST be explicit in the
  tool contract and disabled unless enabled by the user.
- **FR-023**: Tools MUST fail with a specific cause on missing paths, denied
  access, and unsupported store types.
- **FR-024**: Users MUST be able to add and remove tools at agent construction.

**Models**

- **FR-025**: Ollama MUST be supported and MUST be the default path when no
  remote provider is configured.
- **FR-026**: OpenAI-compatible third-party providers MUST be supported via
  explicit endpoint and credential configuration, never enabled by install alone.
- **FR-027**: Changing provider MUST require configuration changes only.
- **FR-028**: Installation MUST NOT download a large model or create a remote
  API key.

**Removal**

- **FR-029**: All intelligence-companion surfaces MUST be removed from the
  repository rather than deprecated in place: companion HTTP endpoints,
  vendor-specific extraction and ranking, and product copy describing AtBots as
  another system's intelligence layer.

### Key Entities

- **Agent**: The configured, ready-to-run unit a user obtains from the package.
  Holds a model, a toolset, a memory provider, and a set of skills; wraps a
  Pydantic AI agent that remains reachable.
- **Task**: A named, reusable unit of work. Has a description, declared inputs,
  instructions, and a declared output type.
- **Task Run**: One execution of a task. Records inputs, tool calls, and the
  validated result.
- **Skill**: A `SKILL.md` directory of instructions and resources, identified by
  name and description, applied on demand.
- **Tool**: A callable capability exposed to the model, carrying an explicit
  contract including whether it is destructive.
- **Memory Provider**: Any implementation of the store/recall interface. The
  built-in default, a shipped optional integration, or a user-supplied class.
- **Model Provider**: The configured inference path — local (Ollama) or a
  third-party OpenAI-compatible endpoint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with a running local model goes from `pip install` to a
  first successful agent response in under 5 minutes, using only the README.
- **SC-002**: Defining and running a task with a structured output requires no
  more than 10 lines of user code.
- **SC-003**: Swapping the memory backend requires changing configuration only —
  zero lines of task, skill, or tool code.
- **SC-004**: An automated check over the core package's dependency list and
  imports finds zero third-party memory products.
- **SC-005**: Every advertised capability — tasks, skills, memory, file tools,
  data-store tools, local and remote models — is exercised by at least one
  automated test that passes without network access to a paid provider.
- **SC-006**: The public API is documentable on a single page, and every symbol
  on it is reachable from the package root.
- **SC-007**: Every user-facing failure in the acceptance scenarios names both
  the cause and the corrective action.
- **SC-008**: A user familiar with Pydantic AI can pass their existing tools and
  models into AtBots without writing an adapter.

## Assumptions

- Target users are Python developers comfortable with `pip` and virtual
  environments; the package is a library and CLI, not an end-user application.
- Pydantic AI remains the agent runtime; AtBots tracks it rather than abstracting
  over multiple agent frameworks.
- Ollama is the assumed local runtime; users wanting local inference install and
  run it themselves.
- The built-in default memory backend is for local and single-process use.
  Production deployments are expected to configure a real backend.
- Named backends (mem0, AtMem, and others) are documented configuration
  examples. Which, if any, ship as optional extras is a planning decision, not a
  requirement of this spec.
- No hosted service, dashboard, or multi-tenant deployment is in scope.
- Existing code under `src/atbot/` is treated as prior art to be replaced, not a
  baseline to preserve. Companion-era modules are removed.
