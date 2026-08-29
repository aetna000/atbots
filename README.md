# AtBot

AtBot is a general-purpose, memory-native agent that can complete tasks with
tools and skills or serve as the governed memory centre for other agents. It
performs model-backed inference and orchestration while AtMem remains the
authoritative memory and evidence engine.

## Architectural boundary

- **AtBot owns intelligence:** task execution, inference providers, extraction,
  reranking, skills, tools, background maintenance, and agent orchestration.
- **AtMem owns truth:** canonical records, policy, provenance, lifecycle,
  scoping, deletion, audit, verification, and context-exposure receipts.
- AtBot must use AtMem's public Python or MCP interfaces. It must never write
  directly to AtMem SQLite tables.
- Inference models may propose memories; they may not authorize their own
  proposals or bypass AtMem policy.

See [Architecture](docs/architecture.md) for the initial component boundaries.

## Development

During joint local development, install AtMem and AtBot as editable packages:

```bash
python -m pip install -e ..
python -m pip install -e ".[dev]"
```
