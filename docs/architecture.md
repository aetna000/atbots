# AtBot companion architecture

AtBot is AtMem's model-backed intelligence component, not an independent
product agent.

```text
OpenClaw, Hermes, or another agent
            <-> agent-specific adapter
            <-> AtMem authority and storage
            <-> AtBot intelligence companion
```

## Responsibility split

- AtBot proposes facts, entities, relationships, query expansions, rankings,
  and maintenance actions.
- AtMem authorizes, stores, retrieves, revalidates, injects, audits, corrects,
  and forgets.
- Adapters authenticate host events and deliver AtMem-authorized context.
- The host agent remains responsible for general conversation and tasks.

> AtBot proposes and ranks; AtMem authorizes and stores.

AtBot sees memory content only after AtMem candidate eligibility. Returned
rankings may contain only IDs from the immutable eligible candidate set. AtMem
revalidates every selection before producing byte-stable context.

## Product interface

The AtMem dashboard is the only customer interface. It contains a chat-style
governed-memory query surface and keeps all authority controls, including
shadow mode, agent topology, review, provenance, correction, forgetting,
storage, vectors, audit, restore, and OpenClaw bridge verification.

The AtBot loopback service is a headless companion protocol endpoint. It has no
separate customer dashboard and no independent canonical database.

## Runtime packages

- `providers`: local-first Pydantic AI model adapters and deterministic fallback.
- `extraction`: strict fact, entity, relationship, and sensitivity proposals.
- `prompts`: stable companion prompts and cache identity.
- `runtime`: bounded memory inference and ranking orchestration.
- `capabilities`: internal hooks, policies, tools, skills, and guardrails used
  only for memory work.
- `service`: companion health, inference, query-expansion, and ranking protocol.
- `gateway`: development/conformance client for AtMem public contracts; AtMem
  remains the only durable authority.

The old independent task loop may remain temporarily as unexposed internal
code during migration, but it is not a supported CLI mode or product surface.

## Failure behavior

When AtBot is unavailable, AtMem continues with deterministic extraction and
lexical, graph, and local-vector ranking. Failure reduces intelligence and
never weakens scope, sensitivity, egress, lifecycle, or audit policy.
