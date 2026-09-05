# AtBots

**Pydantic AI, already set up.** AtBots is a thin layer over
[Pydantic AI](https://ai.pydantic.dev) that ships with tasks, skills, and
memory wired together, as a library and a CLI.

```bash
pip install atbots
```

AtBots is a general-purpose agent package. It is not a sidecar, an extraction
worker, or the intelligence layer for any other product.

## The three pillars

| Pillar | What it gives you |
|--------|-------------------|
| **Tasks** | Named, reusable units of work with declared inputs and typed results. Run them from code or the CLI; inspect what ran. |
| **Skills** | `SKILL.md` directories the agent discovers and applies on demand. Extend the agent by writing documents, not code. |
| **Memory** | A pluggable provider interface. A local default works out of the box; any backend that implements the interface is equally supported. |

## Thin layer, on purpose

AtBots contributes defaults and wiring — instructions, toolsets, skill loading,
memory binding, model routing, a CLI. Pydantic AI keeps the agent loop, model
calls, tool dispatch, and structured output.

That means:

- The underlying Pydantic AI `Agent` is reachable; use any upstream feature directly.
- Your existing Pydantic AI tools, toolsets, and model objects work as-is — no adapters.
- If AtBots wraps something Pydantic AI already does well, that's a bug.

## Models

Ollama is the default when no remote provider is configured, so local work needs
no vendor. OpenAI-compatible providers are first-class and require an explicit
endpoint and credentials — installing AtBots never downloads a large model or
creates an API key on your behalf. Switching providers is a configuration
change; tasks, skills, and tools are untouched.

## Configuring memory

Memory is a **port, not a vendor**. Core `atbots` depends on no third-party
memory product. It defines a provider interface — store and recall, sync and
async — and ships a local default so a fresh install works immediately.

Point it anywhere by satisfying that interface:

- the **built-in default** — local, no account, no external service;
- **mem0**, **AtMem**, or another hosted or self-hosted memory service;
- a **vector store** you already run;
- **your own class**, if none of the above fit.

Swapping backends changes configuration only. Your task, skill, and tool code
does not change. Backends that need an extra dependency install as extras and
fail with a clear message naming the missing package if it isn't present.

<!-- Backend-specific setup snippets land here once the provider interface is
     implemented; see specs/002-general-purpose-agent/spec.md. -->

## Spec-driven development

This repository uses [GitHub Spec Kit](https://github.com/github/spec-kit).
Product behavior is specified first; implementation follows those artifacts.

| Artifact | Path |
|----------|------|
| Constitution | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Feature spec | [`specs/002-general-purpose-agent/spec.md`](specs/002-general-purpose-agent/spec.md) |

Grok Build skills live in [`.grok/skills/`](.grok/skills). From the project
directory:

1. `/speckit-constitution` — project principles (ratified, v3.0.0)
2. `/speckit-specify` — what to build
3. `/speckit-clarify` — optional quality gate
4. `/speckit-plan` — how to build it
5. `/speckit-checklist` — optional requirements review
6. `/speckit-tasks` — implementation breakdown
7. `/speckit-analyze` — optional consistency report
8. `/speckit-implement` — execute remaining tasks
9. `/speckit-converge` — close gaps against spec, plan, and tasks

The git extension creates numbered feature branches (`002-…`). Active feature
state is [`.specify/feature.json`](.specify/feature.json), not the checked-out
branch alone.

Requires the Specify CLI (`uv tool install specify-cli`). Integration: Grok
Build (`specify init --here --integration grok`).

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## License

AtBots is licensed under the [Apache License 2.0](LICENSE). It permits
commercial and internal enterprise use, modification, and distribution,
subject to the license terms. Apache-2.0 also provides an explicit contributor
patent grant and does not require an organization to publish private changes
merely because it runs the software as a service.
