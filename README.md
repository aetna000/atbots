# AtBots

**Pydantic AI, already set up.** AtBots is a thin layer over
[Pydantic AI](https://ai.pydantic.dev) that ships with tasks, skills, and
memory wired together, as a Python library with a CLI for setup.

```bash
pip install atbots
```

AtBots is a general-purpose agent package. It is not a sidecar, an extraction
worker, or the intelligence layer for any other product.

## The three pillars

| Pillar | What it gives you |
|--------|-------------------|
| **Tasks** | Named, reusable units of work with declared inputs and typed results. Run them from Python; inspect the trace of what ran. |
| **Skills** | `SKILL.md` directories declared in configuration and discovered when `TaskAgent` starts. |
| **Memory** | Local governed memory, recalled automatically at the start of every task. `0.1.0` ships one backend; see [Configuring memory](#configuring-memory). |

## Quickstart

AtBots runs tasks from Python. The CLI configures and inspects the install; it
does not run tasks in `0.1.0`.

```bash
pip install atbots
ollama pull qwen3:4b
atbots init --model qwen3:4b --num-ctx 8192   # writes ~/.atbots/config.json
atbots status                                  # confirm the model is reachable
```

`atbots status` prints each provider with `available`, and, when it is not,
`unavailable_reason` — for example `model is not installed: ollama pull qwen3:4b`.

Then run a task:

```python
from atbots.agent import TaskAgent
from atbots.config import load_config

agent = TaskAgent(load_config())
result = agent.run("Summarize what you remember about me.")
print(result.answer)     # the answer
print(result.status)     # completed | step_limit | provider_error
print(result.trace)      # every step, tool, and recovery
```

The full CLI is `init`, `status`, `doctor`, and `serve`. `serve` runs a loopback
HTTP companion and is unrelated to running tasks.

## Thin layer, on purpose

AtBots contributes defaults and wiring — instructions, toolsets, skill loading,
memory binding, model routing, a CLI. Pydantic AI keeps model calls, structured
output, validation retries, and tool dispatch inside each step.

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

## Small local models

The task loop is built for 4B-class models. It never asks the model to drive a
native tool-calling protocol; each turn it asks for one small decision — call a
listed tool, or finish — as a constrained output, and treats every failure as
something the model can recover from on the next step rather than as a crash.

```bash
atbots init --model qwen3:4b --num-ctx 8192
```

**Give the model its context window.** Ollama's OpenAI-compatible endpoint
silently ignores a per-request `num_ctx`, so a model advertised as 32k serves
requests at the 4096-token default. Set `num_ctx` on the provider and AtBots
derives a tag — `qwen3:4b-atbots-ctx8192` — that carries the parameter. It is
created once, reuses the parent model's layers, and downloads nothing. Without
`num_ctx`, nothing is provisioned and the server default applies.

`atbots status` reports `serving_model`, `num_ctx`, and `context_provisioned`,
so the window the model is actually running at is visible.

**Settings that matter on a small model:**

| Setting | Default | What it does |
|---|---|---|
| `providers[].num_ctx` | unset | Context window for a local Ollama model |
| `step_retries` | `2` | In-band re-asks when a decision fails validation; these do not consume the step budget |
| `observation_char_limit` | `2000` | Per-observation truncation |
| `observation_window` | `6` | Most recent observations kept in the step prompt |
| `finish_nudges` | `1` | Times a finish that never tried an available tool is pushed back |
| `max_task_steps` | `8` | Step budget for the whole run |
| `provider_failure_limit` | `3` | Consecutive provider failures before the run stops and reports the provider's own error |
| `tool_failure_limit` | `2` | Failures of one tool before the loop stops calling it |

`atbots status` also reports `unavailable_reason`, so a model you have not
pulled yet says `model is not installed: ollama pull qwen3:4b` instead of failing
silently on every step.

A run never raises on model or tool misbehaviour. Malformed decisions, invented
tool names, refused tools, and failing tool handlers all become observations the
model reads on its next step; the run ends with a status and a trace either way.

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
In `0.1.0`, the task runtime discovers skill names, but the installed
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

## Configuring rules, guardrails, hooks, and Pydantic AI tools

AtBots can load native Pydantic AI capabilities from Python modules or files.
A capability can bundle instructions and tools; Pydantic AI `Hooks` can enforce
guardrails and observe or modify every stage of a model run.

Create `~/.atbots/capabilities/project_policy.py`:

```python
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability, Hooks
from pydantic_ai.exceptions import ToolFailed


project_rules = Capability(
    id="project-rules",
    instructions=(
        "Keep answers concise. Never claim that a task succeeded without a "
        "tool result proving it."
    ),
)


@project_rules.tool_plain
def project_status(project: str) -> dict[str, str]:
    """Return the status of a project."""
    return {"project": project, "status": "active"}


safety_hooks = Hooks(id="project-safety")


@safety_hooks.on.before_run
async def log_run(ctx: RunContext[Any]) -> None:
    print("AtBots run started")


@safety_hooks.on.before_tool_execute
async def block_production_deletes(
    ctx: RunContext[Any],
    *,
    call: Any,
    tool_def: Any,
    args: dict[str, Any],
) -> dict[str, Any]:
    if tool_def.name == "delete_record" and args.get("environment") == "production":
        raise ToolFailed("Deleting production records is forbidden by project policy.")
    return args
```

Reference the exported capability objects in `~/.atbots/config.json`:

```json
{
  "pydantic_capabilities": [
    "~/.atbots/capabilities/project_policy.py:project_rules",
    "~/.atbots/capabilities/project_policy.py:safety_hooks"
  ]
}
```

Installed Python modules work too:

```json
{
  "pydantic_capabilities": [
    "my_agent_policy:rules",
    "my_agent_policy:guardrails"
  ]
}
```

Each reference must resolve to a Pydantic AI `Capability`, `Hooks`, or another
`AbstractCapability` instance. AtBots passes them through the native
`capabilities=` argument whenever it creates a Pydantic AI agent. This gives
extensions access to native instructions, function tools, toolsets, model and
tool hooks, output validation hooks, deferred approval, and capability events.
Invalid references stop the run with a clear configuration error.

AtBots also retains its own outer task lifecycle hooks. Register these directly
with `agent.hooks.add(handler)` to receive `task.started`, `tool.completed`,
`task.finished`, and `task.stopped`. The configured Pydantic AI hooks operate
inside each model run and provide the finer-grained control intended for user
guardrails.

Built-in boundaries remain active around extensions: `allowed_tools` limits
AtBots' outer task tools, `max_task_steps` bounds its task loop, remote egress
requires explicit permission, sensitive content is kept local, tool results are
size-limited, and the HTTP companion only binds to loopback.

## Configuring memory

Memory is a pluggable port. `0.1.0` ships a single backend, AtMem, and stores
memory in `~/.atbots/atmem.db` by default. Change `memory_path` in `~/.atbots/config.json` to use
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
planned, but is not implemented in `0.1.0`.

## Evals

Unit tests answer "is the harness correct". Evals answer "does a small model
actually succeed, how often, and how hard did the harness have to work". They are
two tiers because harness correctness is deterministic and model behaviour is
statistical, and one suite cannot be both.

```bash
pip install -e ".[dev]"        # includes the eval extra

python -m pytest -q            # tier 1 runs here, tier 2 does not
python -m evals.tier1          # tier 1 report
python -m evals.tier2          # tier 2 report, needs Ollama
python -m pytest -m eval       # tier 2 as tests
```

**Tier 1 — the gate.** Scripted model behaviour, no network, under a second. It
drives the real loop through malformed decisions, invented tool names, repeated
calls, oversized tool results, and failing tools, and checks the grounded answer
still comes out. It runs on every commit.

**Tier 2 — the measurement.** The same scenarios against a real local model,
repeated N times, reported as rates and compared to `evals/baseline.json` with an
explicit tolerance. It is excluded from the default gate, and skips with a reason
when Ollama or the model is missing. A measurement used as a pass/fail gate
becomes noise people learn to ignore.

Each run is scored on four assertions and four metrics:

| Scored | What it catches |
|---|---|
| `Completed` | The run reached an answer rather than a budget or provider failure. |
| `Grounded` | The answer quotes the values the fixture tools produced. |
| `NoFabrication` | The answer quotes no plausible value the fixtures never produced. |
| `ToolCoverage` | The required tools actually ran — read from the trace, not the answer. |
| `steps`, `recoveries`, `tools_called`, `peak_prompt_chars` | How much work the harness did, and whether the step prompt still fits the window. |

`Grounded` and `NoFabrication` are separate on purpose. The defect that motivated
these evals was a 1.7B model answering *"free disk space is 10 gigabytes"*
without calling the tool: the run reported `completed`, nothing raised, and the
number was invented. `evals/scenarios.py` keeps that exact case as a negative
control, and Tier 1 asserts the suite still fails it — a suite that cannot catch
its own motivating defect is not measuring anything.

Evaluators are deterministic; nothing here asks a model to judge a model. Add a
scenario by appending to `SCENARIOS` in `evals/scenarios.py`.

Configure Tier 2 with `ATBOTS_EVAL_MODEL` (default `qwen3:4b`),
`ATBOTS_EVAL_NUM_CTX` (default `8192`), and `ATBOTS_EVAL_REPEAT` (default `3`).
Record a new baseline with `python -m evals.tier2 --record`.

## Spec-driven development

This repository uses [GitHub Spec Kit](https://github.com/github/spec-kit).
Product behavior is specified first; implementation follows those artifacts.

| Artifact | Path |
|----------|------|
| Constitution | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Feature spec | [`specs/001-general-purpose-agent/spec.md`](specs/001-general-purpose-agent/spec.md) |
| Small-model harness | [`specs/003-small-model-harness/spec.md`](specs/003-small-model-harness/spec.md) |
| Evals | [`specs/004-evals/spec.md`](specs/004-evals/spec.md) |

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
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

Use a clean virtual environment. The suite includes a check that every installed
dependency satisfies the version declared in `pyproject.toml`, so a stale
environment fails fast rather than testing a version AtBots does not ship.

## License

AtBots is licensed under the [Apache License 2.0](LICENSE). It permits
commercial and internal enterprise use, modification, and distribution,
subject to the license terms. Apache-2.0 also provides an explicit contributor
patent grant and does not require an organization to publish private changes
merely because it runs the software as a service.
