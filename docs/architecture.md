# AtBot architecture

## Responsibility split

```text
Users and agent runtimes
          |
          v
AtBot task runtime or shared memory centre
          |
          v
Tools, skills, inference and retrieval orchestration
          |
          v
AtMem public APIs and control contracts
          |
          v
Canonical memory, provenance, policy and evidence
```

AtBot is independently deployable, but AtMem is its only authoritative memory
store. Derived model output remains a proposal until AtMem admits it under the
configured policy.

## Planned packages

- `agent`: independent general-purpose task-agent runtime
- `memory_centre`: capture, inference, recall, and service orchestration for
  other agents
- `adapters`: runtime hooks for supported agent hosts
- `extraction`: context assembly and model-backed memory proposals
- `providers`: local and remote inference providers
- `retrieval`: governed search fusion, reranking, and context construction
- `skills`: memory operating procedures exposed to agents
- `tools`: typed agent and operator tools
- `workers`: consolidation, contradiction review, and maintenance

## Non-negotiable invariants

1. Other agents cannot mutate canonical storage directly.
2. Model inference cannot approve its own memory proposals.
3. Every active memory remains linked to source evidence.
4. Retrieval is scoped before ranking.
5. Context injection is authorized and receipted by AtMem.
6. Forgetting reaches every AtBot-owned derived representation.
