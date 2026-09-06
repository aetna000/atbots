# Implementation Plan: Small-Model Task Harness

**Branch**: `003-small-model-harness` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-small-model-harness/spec.md`

## Summary

Make the existing bounded task loop survive a 4B model. Four changes: request the
per-step decision as a Pydantic AI constrained output with upstream retries
instead of a schema pasted into the prompt; convert every model and tool failure
from an exception into an observation the model can recover from; give the local
Ollama model the context window the user asked for; and hold the prompt inside a
budget a 4B model can actually read.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: `pydantic-ai-slim[openai]>=2.40,<3`, Ollama on loopback.
Verified against 2.40.0; the major cap matches the project's `atmem>=2.1,<3`
convention, and the 1.x→2.x break (`model.profile` went from dataclass to dict)
shows why it is needed.

**Storage**: N/A (configuration in `~/.atbots/config.json`)

**Testing**: pytest, with provider and tool doubles; no live model required

**Target Platform**: Local developer machine, macOS/Linux

**Project Type**: Single Python package (`src/atbots`)

**Performance Goals**: A step prompt that fits in an 8k window alongside the
model's own reasoning output

**Constraints**: No live-model dependency in tests; no new required
configuration; no second agent loop

**Scale/Scope**: Five existing modules touched, two added

## Findings That Drive the Design

Measured against a live Ollama 
(`qwen3:1.7b`, the same family and a harder case than `qwen3:4b`):

1. `POST /v1/chat/completions` with `options: {"num_ctx": 16384}` loads the model
   at **4096**. The field is dropped by the OpenAI-compatible layer.
2. `POST /api/chat` with the same options loads at **16384** — but a subsequent
   OpenAI-compatible call evicts it and reloads at 4096, so preloading does not
   survive.
3. A model tag created with `PARAMETER num_ctx 16384` loads at **16384** through
   the OpenAI-compatible endpoint.

Therefore the only mechanism that raises the window while keeping Pydantic AI's
OpenAI path is a derived model tag. AtBots provisions it; the user does not write
a Modelfile.

4. Pydantic AI's **default structured-output mode is `tool`**, and Ollama cannot
   serve it. Re-verified on both versions: on `pydantic-ai-slim` 1.107.5 it fails
   as `400 invalid message content type: <nil>`; on 2.40.0 — the declared floor —
   it fails as `UnexpectedModelBehavior: Exceeded maximum output retries`. The
   symptom changed, the incompatibility did not. `NativeOutput` (a JSON-schema
   `response_format`) and `PromptedOutput` both work on both versions. This is the literal
   mechanism behind "small models can't do tool loops" — the failure is in the
   output protocol, not the model. AtBots therefore requests `NativeOutput` and
   falls back once, permanently, to `PromptedOutput` for servers that cannot
   honour a JSON-schema response format.

Also measured: Ollama returns Qwen reasoning in a separate `reasoning` field
rather than inline `<think>` tags, and it honours `response_format` with a JSON
schema. Constrained output is therefore available on the default local path.
Inline `<think>` stripping is still applied, because llama.cpp and LM Studio —
both valid OpenAI-compatible endpoints — do inline it.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Installable package | Unchanged; no new surface, no service. |
| II. Thin layer over Pydantic AI | **Improves compliance.** Hand-rolled schema-in-prompt and hand-rolled JSON parsing are replaced by upstream `output_type` and `retries`. No new message format or tool protocol is added. |
| III. Memory is a pluggable port | Untouched. |
| IV. Tasks, skills, tools | Tool contract unchanged; destructive tools stay refused. |
| V. Local and third-party models | **Directly serves it.** The zero-config local default becomes usable. Provisioning is local-only, triggered by explicit configuration, and downloads nothing — a derived tag reuses existing layers. |

**Pre-existing deviation, not introduced here**: `agent.py` runs an AtBots-owned
step loop rather than delegating to Pydantic AI's own tool loop. That is what
makes small-model operation possible, since the upstream loop assumes reliable
native tool-calling. This plan does not deepen the deviation — it moves the
per-step model call onto upstream primitives. Replacing the loop entirely with a
Pydantic AI toolset belongs in its own feature.

## Project Structure

### Documentation (this feature)

```text
specs/003-small-model-harness/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
src/atbots/
├── agent.py            # recovery, budget, repeat detection
├── capabilities.py     # observation truncation limit becomes a parameter
├── cli.py              # --num-ctx on init; context reporting in status
├── config.py           # num_ctx, step_retries, observation limits
├── steps.py            # NEW: TaskStep output type
├── providers/
│   ├── base.py         # output_type on the provider protocol
│   ├── local.py        # accepts and ignores output_type
│   ├── ollama_ctx.py   # NEW: idempotent derived-tag provisioning
│   ├── pydantic_ai.py  # constrained output, retries, think-stripping, ctx
│   └── router.py       # passes the new provider settings through
tests/
└── test_small_model_harness.py   # NEW
```

**Structure Decision**: The existing single-package layout is kept. Two new
modules are added rather than growing `agent.py` and `pydantic_ai.py`: the output
type is shared between the loop and the deterministic fallback, and context
provisioning is Ollama-specific and must stay isolable from the inference path.

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| `ollama_ctx.py` derived tag | Only mechanism that raises the window over the OpenAI-compatible path | Passing `num_ctx` per request is silently ignored (measured); asking the user to write a Modelfile is the manual step this feature exists to remove |
| `steps.py` output type | Required to use upstream `output_type`/`retries` | Keeping the JSON-Schema-in-prompt approach is the defect being fixed |
| Recovery observations | Small models misbehave per step, not per run | Raising is current behaviour and is the reported failure |
| Output-mode fallback | Ollama rejects upstream's default tool-mode structured output | Pinning one mode strands either Ollama or servers without JSON-schema support |
| Bounded finish push-back | A 1.7B model answered "10 GB" from priors without calling the tool | Prompt wording alone did not stop it; the push-back is capped at one step |
