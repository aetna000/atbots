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
| **Skills** | `SKILL.md` directories declared in configuration and discovered when `TaskAgent` starts. |
| **Memory** | Local governed memory stored by the bundled AtMem backend. |

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

## Configuration directory

New installations keep user configuration and local state in `~/.atbots/`:

```text
~/.atbots/
├── config.json
├── atmem.db
└── skills/
    └── example-skill/
        └── SKILL.md
```

Earlier development builds used `~/.atbot/` because the project originally had
the singular name AtBot. AtBots now uses the plural `~/.atbots/` path to match
the package and command. Existing `~/.atbot/config.json` files remain readable
for compatibility; run `atbots init --force` to create a new plural-path config.

## Adding skills

Create one directory per skill. Each skill must contain a file named exactly
`SKILL.md`:

```bash
mkdir -p ~/.atbots/skills/code-review
```

```markdown
# Code review

Review changes for correctness, security, and missing tests.
```

Save that Markdown as `~/.atbots/skills/code-review/SKILL.md`, then add the
skills root to `~/.atbots/config.json`:

```json
{
  "skill_directories": ["~/.atbots/skills"]
}
```

AtBots scans `<skills-root>/<skill-name>/SKILL.md` when `TaskAgent` is created.
In `0.1.0a1`, the task runtime discovers skill names, but the installed
`atbots serve` companion does not yet execute skill instructions. Full skill
instruction injection is tracked by the general-purpose-agent specification.

## Adding tools

Tools are Python callables registered on a `TaskAgent`. A tool must also appear
in `allowed_tools`; registration alone does not grant permission to run it:

```python
from atbots.agent import TaskAgent
from atbots.capabilities import Tool
from atbots.config import AtBotConfig

config = AtBotConfig(allowed_tools=["memory_recall", "get_weather"])
agent = TaskAgent(config)
agent.tools.register(
    Tool(
        name="get_weather",
        description="Get the current weather for a city.",
        input_schema={
            "type": "object",
            "required": ["city"],
            "properties": {"city": {"type": "string"}},
        },
        handler=lambda arguments: {"city": arguments["city"], "temperature": 22},
    )
)

result = agent.run("What is the weather in Sydney?")
print(result.answer)
```

The built-in `memory_recall` tool is registered automatically. Custom tool
registration is currently a Python API; there is no drop-in tools directory.

## Adding hooks

Hooks observe task lifecycle events. Register a synchronous handler on the
agent before calling `run`:

```python
from atbots.agent import TaskAgent
from atbots.config import AtBotConfig

agent = TaskAgent(AtBotConfig())

def report_event(event: str, payload: dict[str, object]) -> None:
    print(event, payload)

agent.hooks.add(report_event)
result = agent.run("Summarize what you remember")
```

The current task loop emits `task.started`, `tool.completed`, `task.finished`,
and `task.stopped`. Payloads contain trace metadata such as run IDs, step
numbers, and tool names; they do not contain memory or tool-result content.
There is currently no hooks directory or configuration-file hook loader.

## Guardrails

Guardrails are enforced in code around tool and model execution:

- `allowed_tools` is an allowlist. A registered tool cannot run unless its name
  is also present in the configuration.
- Tools declared with `destructive=True` are rejected by the current runtime.
  A separate approval mechanism is planned but not implemented yet.
- Tool results are JSON-serialized and truncated to 20,000 characters before
  they are returned to the model.
- `max_task_steps` limits the task loop to eight steps by default.
- Remote providers require both `remote=True` on the operation and
  `remote_egress_allowed=true` in configuration. Sensitive and restricted
  content is never routed remotely.
- The companion HTTP server only binds to a loopback address and requires the
  session CSRF token for write requests.

These are built-in controls. There is currently no drop-in `guardrails/`
directory or custom guardrail registration API.

## Rules and policy

Runtime rules currently come from three places:

1. `~/.atbots/config.json` sets limits and permissions such as `allowed_tools`,
   `max_task_steps`, and `remote_egress_allowed`.
2. System prompts in `atbots.prompts` and the task runtime define model
   behavior.
3. Python policy checks in the tool registry, provider router, memory gateway,
   and companion enforce boundaries that the model cannot override.

For example:

```json
{
  "allowed_tools": ["memory_recall", "get_weather"],
  "max_task_steps": 6,
  "remote_egress_allowed": false
}
```

There is currently no `RULES.md` convention or rules directory. Use a skill for
reusable instructions and configuration or Python checks for boundaries that
must always be enforced.

## Configuring memory

The current alpha uses AtMem as its memory backend. By default it stores memory
in `~/.atbots/atmem.db`. Change `memory_path` in `~/.atbots/config.json` to use
another local database file:

```json
{
  "memory_path": "/absolute/path/to/my-memory.db"
}
```

You can also configure identity boundaries with `subject_id`, `agent_id`, and
`workspace_id`. These values determine which governed memories the runtime can
read and write. The default values are suitable for one local user:

```json
{
  "subject_id": "local-user",
  "agent_id": "atbot-main",
  "workspace_id": "private"
}
```

Support for interchangeable memory providers such as mem0 and custom classes is
planned, but is not implemented in `0.1.0a1`.

## Spec-driven development

This repository uses [GitHub Spec Kit](https://github.com/github/spec-kit).
Product behavior is specified first; implementation follows those artifacts.

| Artifact | Path |
|----------|------|
| Constitution | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Feature spec | [`specs/001-general-purpose-agent/spec.md`](specs/001-general-purpose-agent/spec.md) |

The specification follows this workflow:

1. `/speckit-constitution` — project principles (ratified, v3.0.0)
2. `/speckit-specify` — what to build
3. `/speckit-clarify` — optional quality gate
4. `/speckit-plan` — how to build it
5. `/speckit-checklist` — optional requirements review
6. `/speckit-tasks` — implementation breakdown
7. `/speckit-analyze` — optional consistency report
8. `/speckit-implement` — execute remaining tasks
9. `/speckit-converge` — close gaps against spec, plan, and tasks

The git extension creates numbered feature branches (`001-…`). Active feature
state is [`.specify/feature.json`](.specify/feature.json), not the checked-out
branch alone.

Requires the Specify CLI (`uv tool install specify-cli`).

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
