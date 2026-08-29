# What AtBot needs to become

Status: proposed consumer-side research and implementation plan

This document defines AtBot as a product and system, describes what it expects
from AtMem 2.2, and sets the implementation and evaluation path. AtBot is a
general-purpose, memory-native agent that can also operate as the shared memory
centre for other agents. It is not a second source of memory truth.

## Naming and release baseline

AtMem and AtBot are public product names, not internal codenames. The current
AtMem `main` branch ships 2.1.0; “AtMem 2.2” means its planned next
authority-contract release. AtBot is a separate consumer and agent runtime,
starting at 0.x and depending only on AtMem's public contracts.

## Product thesis

Most agent-memory systems make memory a passive database or a feature embedded
inside one agent. AtBot should instead be a capable agent runtime in which
memory is a first-class, governed asset. The same runtime can serve as the
memory centre for other agents or use tools and skills to perform tasks itself.

AtBot observes authenticated runtime events, interprets what may be worth
remembering, retrieves relevant governed context, and ensures that every
memory mutation or exposure passes through AtMem. When operating independently,
it can accept objectives, plan and execute work, invoke permitted tools and
skills, collaborate with other agents, and use governed memory across tasks.

AtBot should become:

> A host-neutral, model-flexible, memory-native agent that can complete tasks
> using tools and skills, or serve as the governed memory centre for other
> agents, while AtMem enforces canonical memory, policy, provenance, and
> auditability.

## Desired user outcomes

AtBot succeeds when a user can rely on these statements:

- My agents remember useful information across sessions without retaining every
  conversation as active context.
- I can see exactly what is remembered and which source supports it.
- A webpage, tool result, or another agent cannot silently poison my memory.
- Private memory does not cross agent or workspace boundaries.
- I can correct or forget information and verify that derived copies no longer
  influence retrieval.
- I can ask why a memory was retrieved or injected.
- I can run routine memory work locally and permit frontier models only under an
  explicit egress policy.
- I can replace a model provider without replacing or migrating canonical
  memory.
- AtBot can independently complete tasks when I grant it the required tools and
  skills.
- AtBot can use what it learns across tasks without silently granting itself
  permission to rewrite, disclose, or delete canonical memory.
- The same AtBot installation can serve my other agents without forcing them to
  adopt AtBot's task runtime.

## Operating modes

### 1. Sidecar custodian

AtBot runs alongside another agent runtime. Host hooks call AtBot at capture,
model, context, tool, and turn boundaries. AtBot performs extraction and
retrieval work without becoming the host's primary conversational agent.

### 2. Shared memory service

Several registered agents use one AtBot deployment. Agents in the same AtMem
workspace can share the configured subject; isolated workspaces cannot retrieve
one another's memory.

### 3. Independent task agent

The user gives AtBot objectives to complete. Subject to its capability profile,
AtBot can:

- plan and execute multi-step tasks;
- invoke tools and load procedural skills;
- use local or frontier models selected by policy;
- collaborate with or delegate to other registered agents;
- preserve task continuity through governed memory;
- research, analyse, write, code, operate services, or perform other work for
  which explicit tools and skills are installed;
- inspect memory;
- ask what changed and why;
- review candidates and conflicts;
- trace sources and retrieval decisions;
- request correction or forgetting;
- run privacy and integrity checks;
- diagnose poor recall;
- organize memory maintenance.

Independent-agent mode is not subordinate to memory-centre mode. They are
equal product deployments and may run separately or together.

Equal product status does not require equal release timing. AtBot 0.1 proves
the governed memory-centre path first; the independent task loop begins as a
bounded capability in 0.2 and matures in 0.3.

### 4. Background steward

AtBot runs bounded maintenance jobs for duplicate detection, contradiction
review, stale-memory review, index health, source retention, and evaluation.
Maintenance jobs propose changes; they do not silently rewrite canonical state.

### Existing OpenClaw path

AtMem's Safe Switch and OpenClaw takeover are not abandoned. The OpenClaw
plugin becomes the first reference host adapter for AtBot/AtMem's versioned
runtime hooks. Existing copy, shadow, verify, activate, and restore guarantees
remain AtMem responsibilities; AtBot adds model-backed extraction, retrieval,
and orchestration through the same generic adapter boundary.

## Identity and scope semantics

AtBot carries, but never invents authority for, the complete AtMem scope tuple:

- `subject_id`: the person, team, project, or entity the memory is about;
- `agent_id`: the authenticated runtime identity acting in the current flow;
- `workspace_id`: the hard administrative sharing and isolation boundary.

Session, run, turn, and task IDs provide correlation only. They grant no access.
AtMem owns canonical mappings and authorization; AtBot rejects missing or
ambiguous scope before inference, reranking, prompt assembly, or tool use.

## Product principles

1. **Memory is the asset.** Models, frameworks, embeddings, and indexes are
   replaceable processing components.
2. **Models propose; policy decides.** No inference model approves its own
   memory proposal.
3. **Evidence before confidence.** Confidence without a source binding does not
   justify active memory.
4. **Scope before relevance.** AtBot filters identity and workspace eligibility
   before semantic ranking or content exposure.
5. **Local first, not local only.** Sensitive routine work prefers local models;
   explicit policy may allow frontier APIs for harder tasks.
6. **Explain every influence.** AtBot should identify the records, ranking
   signals, policy, model, and receipt behind injected context.
7. **Fail closed on authority.** Provider or adapter failure may reduce recall,
   but must not create ungoverned memory or cross-scope exposure.
8. **No duplicate truth planes.** AtMem remains the sole canonical store.
9. **Agent autonomy is bounded.** Independent operation does not imply
   permission to approve, export, or delete without policy and confirmation.
10. **Evaluation is a product feature.** Extraction, retrieval, safety, and
    lifecycle quality must be continuously measurable.
11. **Tools define practical ability.** AtBot may attempt only work enabled by
    its installed tools, skills, model capabilities, and assigned identity.
12. **Task authority and memory authority are distinct.** Permission to operate
    a browser, repository, or service does not imply permission to mutate or
    disclose canonical memory.

## Capability model

### General agent execution

AtBot must provide a complete but bounded agent runtime:

- objective intake and typed task state;
- planning, execution, reflection, and termination loops;
- tool discovery, validation, invocation, and result handling;
- on-demand skill discovery and loading;
- optional delegation and multi-agent collaboration;
- human approval checkpoints;
- cancellation, deadlines, retry limits, and budgets;
- durable task checkpoints for recoverable work;
- final results with tool, model, memory, and policy evidence.

The runtime must not assume that memory management is the only kind of task.
Memory is AtBot's persistent cognitive and governance layer, while tools and
skills determine what work an AtBot instance can perform.

AtBot should support named capability profiles such as:

- `memory-centre`: serve governed capture and retrieval to registered agents;
- `task-agent`: perform general tasks with an approved tool and skill set;
- `task-agent-read-memory`: perform tasks and retrieve permitted memories;
- `memory-steward`: propose consolidation, correction, and lifecycle changes;
- `memory-admin`: perform explicitly approved destructive or export operations;
- `combined`: run task-agent and memory-centre workloads with distinct
  identities and audit trails.

A deployment may use one process, but each run must carry a distinct identity,
scope, capability set, and memory role. A task agent normally proposes memory
changes; it does not inherit memory-administrator authority.

### Temporary-state retention

Recent-message buffers, task checkpoints, tool artifacts, retry payloads, and
model caches can contain the same sensitive material as canonical memory. They
must not become an undeclared transcript archive.

AtBot therefore needs a versioned retention policy that:

- keeps recent-message buffers memory-only by default with a short bounded TTL;
- persists task checkpoints only when recovery is enabled and records their
  purpose, owner, scope, creation time, and expiry;
- encrypts persisted sensitive state and separates it by subject, agent,
  workspace, and tenant;
- excludes raw private content from traces, eval artifacts, and crash reports;
- applies AtMem correction and forgetting callbacks to buffers, checkpoints,
  caches, and derived artifacts;
- records deletion acknowledgement and surfaces cleanup failures;
- makes retention and remote-provider copies inspectable by the operator.

### Observation

AtBot must accept authenticated, structured events from host adapters:

- user and agent messages;
- model request and response boundaries;
- context prepared and context exposed;
- tool requests and completions;
- turn completion, failure, or cancellation;
- external outcome receipts;
- media observations whose bytes remain host controlled.

AtBot must distinguish trusted user statements, assistant output, copied web or
tool content, model inference, and operator decisions.

### Context-aware inference

AtBot assembles an extraction context containing:

- current source messages;
- a bounded recent-message window;
- related existing canonical memories;
- current and observation dates;
- subject, agent, workspace, session, and turn identity;
- source trust and egress policy;
- selected extraction skill and prompt version.

The output is a typed proposal containing fact text, a proposed fact key,
entities, confidence, sensitivity, source references, related records, and a
suggested lifecycle relationship. AtBot treats fact keys as untrusted grouping
hints and never assumes a key authorizes supersession. Confidence is explicitly
model self-report unless a calibration artifact identifies the model, prompt
version, and fact category.

### Retrieval

AtBot coordinates retrieval without becoming an authority bypass:

```text
AtBot declares reranker, provider, and egress class
  -> AtMem scope, lifecycle, sensitivity, and egress eligibility
  -> lexical, semantic, graph, trust, and recency candidates
  -> optional AtBot reranking
  -> AtMem membership and policy revalidation
  -> bounded context package
  -> exact exposure confirmation
```

AtBot should support direct factual recall, entity-related recall, temporal
questions, multi-hop relationships, and explicit explanations of weak or empty
results. Candidate content cannot be sent to a local or remote reranker until
AtMem has filtered it for that declared egress class. Changing the provider or
egress class requires discarding the candidate set and requesting a new one.

### Lifecycle stewardship

AtBot detects and proposes responses to:

- exact duplicates;
- semantic duplicates;
- additional supporting evidence;
- changed facts;
- contradictions;
- stale or time-limited facts;
- ambiguous entity identity;
- unsupported or poisoned candidates;
- missing or expiring source evidence.

The canonical result is always decided and recorded by AtMem.

### Skills

AtBot uses versioned, on-demand skills for general task procedures and memory
procedures. Skills describe how work is done; they never grant permission.
Initial memory skill families should cover:

- memory review;
- contradiction resolution;
- source investigation;
- privacy audit;
- retrieval diagnosis;
- memory maintenance;
- adapter health investigation;
- deletion verification.

General skills may cover coding, research, document work, operations, data
analysis, browser workflows, or domain-specific tasks. Their availability is a
deployment choice, not a limitation of the AtBot architecture.

Skill selection, loading, model-visible content, and version must appear in
operational traces. Tool access remains governed separately.

### Tools

AtBot should expose separate tool profiles.

Task tools may include:

- filesystem and code-repository operations;
- browser, search, and document operations;
- APIs, databases, messaging, and service control;
- domain-specific tools installed by an operator;
- delegation or communication with other agents.

Task tools must be explicitly granted per agent profile and run. Their outputs
are untrusted observations until validated; possessing a task tool grants no
additional memory authority.

Agent-safe tools:

- recall memory;
- explain retrieval;
- propose memory;
- retrieve an authorized record or source;
- report adapter and memory status.

Operator tools:

- approve or reject candidates;
- resolve conflicts;
- correct or forget memory;
- export authorized evidence;
- configure agents, workspaces, models, and policy;
- activate or return an adapter to shadow;
- run verification and maintenance.

AtBot must never expose operator tools to ordinary agents merely because a
model requests them.

### Policy and guardrails

AtBot needs application guardrails for:

- prompt injection and instruction/data separation;
- secret and PII egress;
- remote-model permission;
- model and tool call budgets;
- structured-output validation;
- tool argument validation;
- destructive-operation confirmation;
- unsupported provider capabilities;
- excessive or recursive agent loops.

AtMem remains responsible for admission, scope, lifecycle, deletion,
retrieval eligibility, and injection authorization.

### Models

AtBot must treat models as replaceable workers selected by capability and
policy. It should support:

- local Qwen and other open-weight models through Ollama or an OpenAI-compatible
  local endpoint;
- direct OpenAI models;
- DeepSeek and other OpenAI-compatible APIs;
- optional routing providers such as OpenRouter;
- deterministic and fake models for tests;
- explicit fallback chains that never weaken data-egress restrictions.

The same model should not automatically extract, approve, answer, and judge its
own work.

### KV- and prompt-cache-aware execution

AtBot must construct prompts so unchanged prefixes remain byte-for-byte
identical and can reuse a local model's KV cache or a remote provider's prompt
cache. Cache awareness is part of the prompt and context architecture, not a
provider-specific shortcut.

The prompt should be assembled in layers from least to most volatile:

```text
stable system and policy instructions
  -> stable tool schemas
  -> stable loaded-skill instructions
  -> authorized byte-stable memory context
  -> recent conversation and task state
  -> current request
```

AtBot must:

- use canonical UTF-8 rendering, fixed separators and newlines, deterministic
  ordering, and versioned serializers;
- keep timestamps, run IDs, receipt IDs, nonces, counters, and other volatile
  values out of a reusable prefix;
- preserve the exact byte order and prompt position of every cached layer;
- bind a cache identity to provider, model, tokenizer, system-prompt version,
  policy digest, tool-schema digest, skill digest, AtMem context digest, scope,
  and memory generation;
- treat changes to any bound value as a cache miss or invalidation;
- isolate local cache entries by subject, agent, workspace, tenant, and
  sensitivity policy;
- obtain current AtMem retrieval and exposure authorization on every use,
  including a cache hit;
- evict affected local entries after correction, supersession, quarantine,
  forgetting, permission changes, or deletion callbacks;
- never reconstruct forgotten or newly ineligible memory from cached tokens,
  hidden state, stored prompts, traces, or retry artifacts;
- use provider-side caching only when egress, retention, data-location, and
  provider policy permit it;
- record cache eligibility, hit/miss, prefix digest, token count, saved latency,
  saved input tokens, and invalidation reason without logging private content.

AtMem supplies the authorized byte-stable memory block and canonical digest.
AtBot owns complete prompt assembly and any provider or local KV-cache handle.
Byte stability makes reuse possible; it never makes a stale cache entry safe.

### Evals and observability

AtBot needs three complementary evidence layers:

- unit and contract tests for deterministic control behavior;
- Pydantic Evals for extraction, retrieval, trajectory, safety, and model
  comparisons;
- OpenTelemetry for latency, token, provider, skill, tool, and failure traces;
- AtMem audit and Agent Black Box for authoritative memory/exposure evidence.

Operational traces must exclude raw private content by default. Record IDs,
digests, policy versions, and bounded safe metadata should correlate AtBot
traces with AtMem receipts.

## System components

AtBot should evolve toward these internal components:

```text
service
  host API, task API, interactive API, worker lifecycle

agent runtime
  objectives, plans, loops, checkpoints, delegation, results

identity
  authenticated agent/workspace/session/run/turn context

gateway
  the only package permitted to call AtMem

context assembler
  recent messages, related memory, dates, scope, budgets

prompt assembler
  canonical byte-stable layers, cache keys, dynamic suffixes

cache manager
  provider/local KV reuse, scope isolation, invalidation, metrics

extractor
  typed fact/entity/relationship proposals

retriever
  candidate requests, optional reranking, explanations

model router
  capability, privacy, cost, latency, and fallback policy

skills
  general and memory-specific procedural instructions

tools
  task, agent-safe memory, and operator-only typed operations

guardrails
  input, tool, output, egress, and budget controls

workers
  bounded maintenance and evaluation jobs

observability
  OTel spans correlated with AtMem evidence
```

## Product surfaces

AtBot should eventually provide:

- a Python SDK;
- host-neutral HTTP or local RPC hooks;
- MCP surfaces for agent-safe and operator operations;
- a CLI for status, diagnosis, evaluation, and service lifecycle;
- an interactive local AtBot task and chat interface;
- adapter packages for supported runtimes;
- a review and investigation UI using AtMem's canonical operations;
- exportable evaluation and trace reports.

The first release does not need all surfaces. Its production focus is a local
memory-centre service plus Python client and a minimal memory inspection CLI.
The independent task-agent interface remains part of the architecture but is
introduced after the memory authority boundary is proven.

## Trust boundaries

AtBot must label every important input according to assurance:

| Input | Default assurance |
| --- | --- |
| authenticated user message from verified adapter | trusted source statement |
| assistant/model output | model generated |
| tool result | external observation |
| webpage/document text | untrusted external content |
| AtBot extraction | model interpreted |
| operator decision | authenticated administrative action |
| external outcome receipt | verifier dependent |

AtBot cannot prove that a generic host hook reported truthfully. It records the
adapter and assurance, while AtMem preserves the distinction in evidence.

## Failure behavior

AtBot must define safe behavior for:

- local model unavailable;
- remote provider unavailable or rate limited;
- malformed structured output;
- extraction timeout;
- AtMem unavailable;
- stale candidate set;
- exposure mismatch;
- cancelled turn;
- duplicate event replay;
- partial tool execution;
- worker crash during maintenance.

The default response is degradation, quarantine, retry with bounded policy, or
operator attention—not silent memory mutation.

## Non-goals

AtBot should not become:

- a replacement canonical database for AtMem;
- an agent whose general tools or task identity bypass memory policy;
- a provider-specific wrapper around one model API;
- a transcript archive presented as durable memory;
- an autonomous approver of sensitive memory;
- a public multi-tenant SaaS before identity, storage isolation, retention, and
  encryption responsibilities are explicitly implemented;
- a system that claims factual truth because hashes or model confidence verify.

## Initial release definition

AtBot 0.1 should deliver one complete memory-centre vertical slice:

1. Run locally as a memory-centre service.
2. Register one generic agent and workspace.
3. Receive one authenticated user-message capture.
4. Use a local model to produce a typed proposal.
5. Submit the proposal through AtMem 2.2 admission.
6. Retrieve governed context for a later query.
7. Optionally rerank only AtMem-eligible candidates.
8. Return an authorized context package.
9. Confirm the exact context exposure.
10. Produce correlated OTel traces and AtMem audit evidence.
11. Let the user inspect the memory and its source through AtBot.
12. Pass extraction, scope-leakage, poisoning, replay, and deletion tests.
13. Prove with a synthetic task identity that ordinary agent authority cannot
    directly approve, export, delete, or disclose memory outside its assigned
    scope.

## Product maturity roadmap

### AtBot 0.1: trustworthy vertical slice

- one generic adapter;
- local model extraction;
- typed proposals;
- governed recall and exposure;
- basic interactive inspection;
- separate task and memory capability identities;
- baseline eval and trace suite.

### AtBot 0.2: model intelligence

- recent-message context;
- entity and temporal proposals;
- semantic reranking;
- contradiction analysis;
- controlled OpenAI and DeepSeek escalation;
- bounded independent task loop with one approved tool and skill;
- memory-aware task execution with no authority escalation;
- model-quality comparison reports.

### AtBot 0.3: multi-agent and capable task execution

- several agents and workspaces;
- shared and isolated memory policies;
- adapter capability negotiation;
- agent-safe tools and skill catalog;
- cross-agent leakage and topology evals;
- durable multi-step task execution;
- broader typed tool and skill catalogs;
- approval, cancellation, checkpoint, and recovery flows;
- optional delegation to registered agents;
- task trajectory and outcome evals;
- memory-aware task continuity without authority escalation.

### AtBot 0.4: autonomous stewardship

- bounded maintenance workers;
- stale-memory and conflict review;
- source-retention monitoring;
- deletion acknowledgement;
- operator review experience.

### AtBot 1.0: production memory-native agent

- stable public SDK and protocols;
- supported adapter lifecycle;
- versioned skill and policy compatibility;
- privacy-safe observability;
- documented backup, recovery, and upgrade paths;
- published evaluation methodology and release gates;
- no direct dependency on AtMem internals;
- supported independent-agent and memory-centre deployment profiles;
- stable task, tool, skill, delegation, and checkpoint contracts.

## Success measures

AtBot should publish and gate releases on measurable outcomes:

- extraction precision and recall;
- unsupported-memory rate;
- source-link completeness;
- duplicate and contradiction-handling accuracy;
- retrieval recall at fixed context budgets;
- incorrect-injection rate;
- cross-scope leakage rate;
- poisoning activation rate;
- forgetting completeness;
- local-versus-frontier quality, latency, tokens, and cost;
- byte-stable prefix reproducibility and cache-hit rate;
- cached input-token, latency, and local-prefill savings;
- stale, forgotten, or cross-scope cache-reuse rate, which must remain zero;
- task completion and verified outcome rate;
- tool-call correctness and unnecessary-tool-call rate;
- approval bypass and unauthorized-action rate;
- checkpoint recovery and cancellation correctness;
- hook/event closure;
- human review burden;
- percentage of injected context with valid AtMem receipts.

No single aggregate score should hide a safety regression. Scope leakage,
forgotten-memory retrieval, and unreceipted injection should be release-blocking
failures.

## Open research questions

- What minimum local model produces acceptable extraction precision on target
  hardware?
- Which memory categories may be automatically activated, and which always
  require review?
- How should AtBot bind one extracted fact to exact source-message spans without
  overstating model precision?
- When does semantic reranking improve recall enough to justify content egress
  or local compute?
- How should temporal facts expire or request review without losing history?
- Which entity merges can be deterministic, and which require confirmation?
- How should multiple agents report conflicting observations about one subject?
- What trace content is necessary for diagnosis without duplicating sensitive
  memory outside AtMem?
- Which operations need durable execution rather than a bounded local worker?
- What is the smallest stable host adapter contract that can be implemented
  honestly across different runtimes?
- Which prompt layers remain stable enough to cache across turns and tasks
  without reducing retrieval quality?
- Which supported local runtimes and remote providers expose reliable cache
  controls and cache-hit telemetry?

## Core rule

```text
AtBot owns intelligence and orchestration.
AtMem owns canonical memory and memory authority.
```

AtBot must remain independently deployable. It may run beside other agents or
as a task agent itself. Any mode that uses long-term memory goes through the
same AtMem gateway and receives no direct database bypass. AtBot's policy layer
separately governs its non-memory tools and task actions.

## AtMem 2.2 capabilities AtBot depends on

AtBot development depends on the following versioned AtMem contracts:

1. memory proposal and admission;
2. source episode/message references;
3. contradiction and supersession relationships;
4. eligible hybrid-recall candidate sets;
5. external reranker validation;
6. context preparation and exact exposure confirmation;
7. generic capture/model/tool/turn hooks;
8. complete forget cascade and external cleanup acknowledgement;
9. agent/workspace scope enforcement;
10. idempotency, concurrency, and crash-safe audit mutation;
11. canonical byte-stable context serialization, generation digests, and
    invalidation signals.

The detailed authority-side requirements live in AtMem's
`research/research.md` and should be treated as the source contract for the 2.2
milestone.

## AtBot responsibilities

AtBot will build the capabilities that deliberately remain outside AtMem:

- objective intake, planning, execution, reflection, and termination loops;
- typed task state, checkpoints, cancellation, retry, and recovery;
- general tool discovery, permission checks, execution, and result handling;
- general and memory-specific skill discovery and loading;
- optional delegation and multi-agent collaboration;
- recent-message buffers and extraction context assembly;
- byte-stable prompt assembly and scope-bound KV/prompt-cache management;
- Pydantic AI agent loops and typed output models;
- Ollama/local Qwen and open-weight model support;
- OpenAI, DeepSeek, and other permitted remote providers;
- task-, privacy-, cost-, and capability-aware model routing;
- fact, entity, temporal, and relationship proposal generation;
- model-assisted contradiction analysis;
- semantic/model reranking over AtMem-eligible candidates;
- versioned `SKILL.md` libraries;
- application guardrails and human approval user experience;
- host adapters and an independent task/chat interface;
- maintenance workers and evaluation datasets;
- OpenTelemetry traces and operational dashboards.

## AtBot must not

- create another canonical memory database;
- write directly to AtMem SQLite tables;
- treat vector or graph indexes as canonical memory;
- approve its own model-generated proposals;
- bypass AtMem scope checks or injection authorization;
- use skills as permissions;
- retain remote-provider copies without declared policy;
- claim that a model inference is source-verified when it is not;
- silently continue after AtMem rejects an admission or exposure receipt.

## Proposed AtMem gateway

Only the gateway package imports AtMem implementation or protocol clients:

```python
from typing import Protocol

from atbot.contracts.atmem_v1 import (
    CaptureSourceRequest,
    CaptureSourceResult,
    ContextRequest,
    EligibleCandidateSet,
    EventReceipt,
    ExposureConfirmation,
    ExposureReceipt,
    ForgetReceipt,
    ForgetRequest,
    FinalRanking,
    MemoryAdmission,
    MemoryProposal,
    PreparedContext,
    RecallRequest,
    ReviewRequest,
    ReviewResult,
    RerankProposal,
    RuntimeEvent,
)


class AtMemGateway(Protocol):
    async def capture_source(
        self, request: CaptureSourceRequest
    ) -> CaptureSourceResult: ...
    async def submit_proposal(self, proposal: MemoryProposal) -> MemoryAdmission: ...
    async def eligible_candidates(
        self, request: RecallRequest
    ) -> EligibleCandidateSet: ...
    async def finalize_ranking(self, request: RerankProposal) -> FinalRanking: ...
    async def prepare_context(self, request: ContextRequest) -> PreparedContext: ...
    async def confirm_exposure(
        self, request: ExposureConfirmation
    ) -> ExposureReceipt: ...
    async def review(self, request: ReviewRequest) -> ReviewResult: ...
    async def forget(self, request: ForgetRequest) -> ForgetReceipt: ...
    async def record_event(self, event: RuntimeEvent) -> EventReceipt: ...
```

AtBot domain code depends on this protocol, not on AtMem database classes,
dashboard endpoints, or OpenClaw-specific modules.

The types above are generated from or validated against the immutable JSON
Schema bundle published by AtMem. AtMem is the only schema source. The fake
gateway, fake adapter, real endpoints, and AtBot CI all run the same pinned
conformance fixtures; AtBot does not maintain a second handwritten contract.

## Proposed AtBot flows

### Capture and extraction

```text
authenticated host message
  -> AtMem source capture
  -> AtBot recent-context assembly
  -> related canonical-memory lookup
  -> model extraction into typed proposals
  -> deterministic AtBot validation
  -> AtMem proposal admission
  -> active/quarantined/duplicate/conflict decision
```

AtBot records the exact model, provider, prompt version, source digest, and
whether content left the local machine. An extraction failure produces no
canonical mutation.

### Retrieval and injection

```text
host query
  -> AtBot declares intended reranker and egress class
  -> AtMem scope, lifecycle, sensitivity, and egress filtering
  -> eligible lexical/semantic/graph candidates
  -> optional AtBot reranking
  -> AtMem final ranking validation
  -> AtMem bounded context package
  -> host injects only when authorized
  -> AtBot/host confirms exact exposure digest
```

AtBot cannot add records that AtMem did not mark eligible.
It also cannot change reranker provider or egress class after candidate
disclosure without obtaining a newly filtered candidate set.

### Contradiction handling

```text
new proposal + related active records
  -> AtBot relationship analysis
  -> typed contradiction/supersession suggestion
  -> AtMem policy decision
  -> automatic safe transition or review queue
```

AtBot never edits an old record in place.

### Forgetting

```text
authorized forget request
  -> AtMem canonical and derived cascade
  -> AtBot receives cleanup request for its caches/artifacts
  -> AtBot deletes or invalidates derivatives
  -> AtBot returns cleanup acknowledgement
  -> AtMem issues the composite receipt
```

## Pydantic AI role

Pydantic AI is an AtBot implementation dependency, not part of the AtMem
protocol. AtBot will use it for:

- typed extraction and relationship outputs;
- local and remote model adapters;
- agent loops and dependency injection;
- model, tool, output, and event hooks;
- function tools, toolsets, and MCP;
- on-demand Agent Skills;
- input, output, and tool guardrails;
- deterministic test models and Pydantic Evals;
- OpenTelemetry instrumentation.

AtBot will wrap Pydantic types behind its own model, tool, skill, hook, and
trace interfaces so a framework change does not affect AtMem contracts.

## Model routing policy

Initial routing intent:

| Task | Preferred route | Escalation |
| --- | --- | --- |
| explicit fact extraction | local Qwen/open-weight model | remote only if policy permits |
| entity and temporal extraction | local model | larger local model |
| routine reranking | local model or deterministic ranker | none by default |
| ambiguous contradiction | larger local model | DeepSeek/OpenAI with allowed egress |
| interactive AtBot | operator-selected | configured fallback |
| evaluation judge | deterministic/local or pinned frontier model over synthetic or explicitly consented data | second permitted judge for disputed cases |

Model selection must check sensitivity, egress permission, structured-output
support, tool support, context limit, cost budget, and prior provider failure.
No remote fallback is automatic for restricted content.
Remote evaluation judges may receive only synthetic datasets or content whose
owner explicitly consented to that provider, purpose, and retention policy.

## Skill design

Initial skills:

```text
memory-review
contradiction-resolution
privacy-audit
source-investigation
memory-maintenance
retrieval-diagnosis
```

The model initially receives only skill names and descriptions. Full
instructions load on demand. Skill loading affects procedure, never AtMem
authorization or tool permissions.

## Guardrail layers

AtBot application guardrails:

- prompt-injection detection;
- PII and secret egress control;
- structured-output validation;
- model/tool call and spending limits;
- approval user experience;
- unsupported capability rejection;
- remote-provider routing constraints.

AtMem authority guardrails:

- source trust and admission policy;
- subject/workspace isolation;
- lifecycle eligibility;
- canonical mutation and deletion;
- retrieval and injection authorization;
- audit and evidence integrity.

AtBot guardrails may reject earlier, but they cannot weaken an AtMem decision.

## Evaluation plan

### Extraction

- durable-fact precision and recall;
- pronoun and reference resolution;
- temporal grounding;
- source-message coverage;
- hallucination and unsupported-inference rate;
- duplicate and overgeneralization rate;
- confidence calibration by pinned model, prompt version, and fact category,
  including Brier score and expected calibration error where confidence affects
  policy.

### Lifecycle

- correct duplicate/conflict/supersession suggestion;
- quarantine precision;
- idempotent replay;
- no partial mutation on provider failure;
- complete source lineage.

### Retrieval

- recall at configured context budget;
- incorrect-injection rate;
- cross-scope leakage rate;
- entity and multi-hop retrieval;
- stale-memory exclusion;
- reranker membership and ordering correctness;
- pre-disclosure sensitivity and egress filtering;
- provider or egress changes requiring a newly filtered candidate set.

### Safety

- indirect prompt-injection resistance;
- private-memory egress prevention;
- approval enforcement;
- forgotten-memory absence;
- skill/tool permission separation;
- remote fallback policy compliance;
- fact-key collision and cross-interpreter supersession containment;
- synthetic-or-consented-only remote evaluation compliance;
- temporary-buffer, checkpoint, cache, and artifact retention compliance.

### Operations

- latency and token/cost distribution;
- local versus frontier model quality;
- byte-for-byte prefix reproducibility across processes and restarts;
- cache hit/miss and invalidation correctness;
- no cache reuse after memory, policy, permission, prompt, tool, skill, model,
  tokenizer, or scope changes;
- no forgotten or cross-scope memory recoverable through cached state;
- hook coverage and event closure;
- trace completeness;
- crash and retry behavior under concurrent agents.

Pydantic Evals and OpenTelemetry support development analysis. AtMem audit and
Black Box evidence remain the authoritative record of memory admission,
retrieval, exposure, and host-reported execution.

## Development sequence

### Phase 0: contract fixture

- pin AtMem's immutable canonical JSON Schema bundle;
- generate or validate AtBot's typed models from that bundle;
- implement an in-memory fake `AtMemGateway` from the same schemas and
  conformance examples used by AtMem's real endpoints and fake AtBot adapter;
- build deterministic Pydantic test-model flows;
- contribute contract failures back to AtMem before implementation hardens.

### Phase 1: minimal vertical slice

- one authenticated message;
- one typed local-model proposal;
- one AtMem admission result;
- one governed recall;
- one exposure confirmation;
- one synthetic ordinary-agent identity denied memory-administrator operations;
- one end-to-end memory, trace, and audit verification.

### Phase 2: intelligence

- recent-context assembly;
- canonical layered prompt assembly and cache-key contract;
- local KV- and remote prompt-cache adapters with invalidation tests;
- entity and temporal extraction;
- hybrid candidate reranking;
- contradiction analysis;
- local/remote model routing;
- one bounded independent task loop with an approved tool and skill.

### Phase 3: agent product

- durable independent task-agent runtime;
- general skills and typed task tools;
- delegation, approval, cancellation, and recovery;
- memory skills and operator tools;
- review experience;
- maintenance workers;
- additional generic host adapters.

### Phase 4: production evidence

- full evaluation gates;
- concurrency and failure testing;
- privacy-safe OTel deployment;
- AtMem Black Box correlation;
- backup, restore, and deletion drills.

## AtBot start gate

General agent-runtime work does not need to wait for AtMem 2.2. AtBot can build
its task loop, tool and skill contracts, capability profiles, model routing,
approvals, checkpoints, and eval harness against an in-memory fake gateway.

Production memory-centre and memory-aware task flows require AtMem's working
proposal/admission and governed-recall contracts. Until those exist, AtBot must
not invent a temporary canonical memory database or couple itself to AtMem
internals.

## Definition of success

AtBot succeeds when it can independently accept objectives, complete bounded
tasks through permitted tools and skills, use governed memory across tasks, and
also serve multiple external agents as their memory centre. It must run local
or frontier inference, propose and rerank memory, and preserve task continuity,
while AtMem can still reject every unsafe proposal, enforce every memory scope,
validate every injected record, forget every derivative, and verify retained
evidence without trusting AtBot's model or task identity.
