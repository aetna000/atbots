# Named agents — 0.3.0b1 beta

Feature 006 is the full agent platform. This guide describes only the current
implemented foundation, not a claim that the remaining platform is complete.
Use a virtual environment and install the beta explicitly:

```sh
python -m pip install --upgrade 'atbots==0.3.0b1'
# Requires an already installed/running local model; no model is downloaded:
atbots --new researcher --model qwen3:4b
atbots researcher
```

`--new` enters chat on a terminal. When stdin is not interactive, it only creates
the agent. `atbots` without arguments opens the control room. `/exit` leaves a
conversation. Both the control room and agents default to local Ollama; they need
a reachable model. Missing inference produces an error, not a fabricated answer.
No background jobs start merely by opening or closing chat.

## Explicit commands and model selection

```sh
atbots agents create researcher --model qwen3:4b
atbots agents list
atbots agents show researcher
atbots chat researcher "Hello"
atbots agents configure researcher --revision 1 --model qwen3:4b-atbots-ctx8192
```

The two create examples are alternatives, not commands to run for the same name.
Model IDs must already be available. Configuration changes advance the revision;
inspect the current value before editing. Reopen chat after changing configuration.
The configured local model's serving context window is used; this new path does
not yet provision an Ollama context tag automatically. Use an existing tag if needed.

Remote example after installing the authentication extra:

```sh
python -m pip install --upgrade 'atbots[auth]==0.3.0b1'
atbots auth login chatgpt
atbots agents create assistant --provider chatgpt --model YOUR_ACCESSIBLE_MODEL_ID --allow-remote
```

Copilot model-provider binding uses `--provider github-copilot`; AtSys coding-CLI
binding will instead use `copilot`. Those are different integrations. Anthropic
uses `.[anthropic]`, `--provider anthropic`, `--api-key-env ANTHROPIC_API_KEY` and
`--allow-remote`, not subscription OAuth. Secret values never belong in arguments
or configuration. Put only environment variable/profile references there.

The control room has its own `control-room` agent, created the first time it opens.
It can use a different model via `agents configure control-room --revision N ...`.
When its model works, ordinary requests such as "create a researcher", "list my
agents", "show researcher configuration" or "ask researcher ..." become typed
operations. Create/configure proposals show the exact changes and require `y`.
These in-process approvals expire after five minutes and disappear on restart;
durable job approvals are a later task, not claimed here. Configure the control
room itself from the explicit CLI, then reopen it to apply its new model.

## Memory and storage

Named agents use separate AtMem databases/scopes by default. In agent chat:

```text
remember: I prefer concise technical answers
```

This is an explicit user-authorized proposal, not model-generated memory text.
AtMem decides admission; later relevant queries receive governed context and an
exposure receipt. Responses are not automatically promoted to verified lessons.
General automatic formation, correction, forgetting, sharing and their UI remain
T004 work. Do not assume every conversational statement is persistently remembered.
Known credential patterns are refused before ordinary model/history/memory capture;
this is not complete detection of every secret or sensitive passage. Native tool
history can contain private material: retain it only on trusted storage and do not
put credentials into conversations or caller-supplied tools. Tool sandboxing,
history export/retention and comprehensive input/output policy are not finished.

Default data root: `~/.atbots/platform`; old `~/.atbots/config.json` is untouched.
Use `atbots --root /an/explicit/private/path agents list` for another root.
Agent definitions and native histories live in `agents.sqlite`; UUID workspaces
contain files/browser directories and lazy-created AtMem databases. They are
storage namespaces, not OS sandboxes. Same-agent turns/configuration are locked;
busy operations fail explicitly rather than interrupting a running turn.

## Native library use

```python
from atbots.platform import AgentStore
from atbots.platform.session import AgentSession

store = AgentStore("/an/explicit/private/path")
store.create("researcher")  # once
session = AgentSession(store, "researcher")
print(session.chat("Hello").text)
native_agent = session.agent  # actual Pydantic AI Agent
```

Native model/tools/toolsets can be supplied at construction. They are trusted
caller-owned execution, not model-generated extensions. Calling the exposed
Agent directly bypasses AtBots persistence/limits; use session.chat for that wiring.
For explicitly classified input, `chat(..., sensitivity="restricted")` refuses a
remote binding. The CLI does not yet infer arbitrary sensitivity from prose.

## Still required before platform completion

Durable background jobs/approvals, full memory controls, browser/vision/file tools,
skills installation, scheduling, AtSys 0.3.0b4 role wiring, optional AtFlows tracing,
cloud deployment and web control room are tracked in feature 006 tasks. AtSys's
provider-parity adapters already exist; AtBots integration is not yet complete.
AtFlows observes calls; it is not a workflow engine. No paid cloud resources were
created and no package release was made for this foundation.


## Experimental beta adapters

The beta also includes jobs/approval receipts, browser/workspace and reviewed
skill tools, schedules, loopback web management, an AtSys adapter, and portable
cloud-state adapters. These go beyond the original foundation described above;
feature 006 tasks remain the full-platform acceptance checklist. Read the
[release notes](releases/v0.3.0b1.md) before enabling them. Source code and
deterministic tests do not establish live cloud, subscription or integration
reliability. The beta does not certify the full feature-006 platform as complete.
