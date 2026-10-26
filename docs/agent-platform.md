# Your agents, under your control

This guide describes the **0.3.0b2 beta**. The older 0.3.0b1 does not contain
these UI corrections. Use Python 3.11+ and pip; a separate environment is recommended:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade 'atbots==0.3.0b2'
atbots
```

The browser opens your control room. Setup itself does not need a running model.
Installation does not download one or make a paid inference request.
For browser-using agents, install `python -m pip install 'atbots[browser]==0.3.0b2'`
and `python -m playwright install chromium` before enabling browser permissions.
Scheduling, provider authentication and the AtSys package are included in the base
installation. The cloud extra is not needed for this local journey.

## Start here: no configuration commands

1. Open **Setup & connections**. Connect ChatGPT/Codex or GitHub Copilot using
   supported account sign-in, or save an OpenAI/Anthropic API key. Keys stay in
   the OS credential store. Copilot's first sign-in needs your own device-enabled
   OAuth application's Client ID; the form links to GitHub's registration page.
2. Choose **Control room model**, select a connection and a discovered model,
   allow remote inference if appropriate, then review and approve. This works
   even when the previous local model is unavailable.
3. Choose **New agent**, give it a name, select the connection/model and review
   visible file/remote permissions. Approve to create its private workspace.
4. Select the agent. **Environment** shows its real working directory, permissions,
   memory backend and integration setup. **Memory** and **Files** inspect only
   this agent. Share provider authentication, never private memories.
5. Open **Supervision**, choose **Start private AtSys**, then choose its worker/
   supervisor CLI and models, acceptance command and trusted-local permission.
   Keep **Initialize Git** checked for a fresh Codex workspace; it does not change
   global Git settings. Save the settings. The AtSys package is included; the
   chosen coding CLI must be installed and signed in. Ask “AtSys, do this” in agent chat; the
   built-in skill and native tool prepare an approval. It has not started until
   the approval returns a real upstream task ID.
6. Use **Schedule** for a one-time task or ask the control room for a recurring
   schedule. Review/approve the exact occurrence and timezone. **Settings** can
   pause an agent or archive it while retaining its data.
7. **Components** shows installed AtMem, AtSys and AtFlows versions. Checking
   available versions uses public PyPI metadata, not inference. To upgrade, pause
   agents and finish/cancel jobs, select an exact compatible version and confirm.
   The app stops only verified, idle, agent-private AtSys services before upgrading.
   Restart the app, then start the private service again before supervised work.
   Delegated work requires separate reconciliation; the UI will not upgrade over
   active or unreconciled tasks. An interrupted/failed pip operation requires
   attention, not a success claim or an automatic rollback.

Opening `atbots` starts one background desktop/runner for this local root.
Closing the browser or launching terminal does not stop it. Reopening reconnects.
The PC must be on and awake; no model calls occur just to keep an idle agent
alive. OS boot auto-start is not installed. Package versions are shared within
this Python environment, while every agent's files/memory/configuration are private.

## Manage by talking

`atbots` (or `atbots ui`) opens the authenticated loopback UI; `atbots control`
opens terminal chat. Do not share the credential-bearing browser URL. Public
hosting/TLS is not implemented; use separately secured port forwarding remotely.

Try “Create a local agent named researcher”, “Show researcher configuration”,
“Ask researcher to explain this project”, “Have researcher work on a report in
the background”, or “Show researcher's jobs”. Select an agent for direct chat.

Mutations show an exact typed proposal for approval. Approvals are persisted,
single-use and expire after five minutes; pending ones return after web reload.
Revisions and memory digests reject stale approvals. An external operation left
`executing` has an unconfirmed outcome: inspect its owner before repeating it.
Plain-language routing depends on the configured model, not a universal guarantee.

The control room has a separate `control-room` model. Choose **Control room model**
in the UI without needing its existing model to run. The **New agent** and
**Settings** forms produce the same durable approvals as conversational requests;
submitting a form does not immediately change permissions or configuration.
**Check setup** runs the read-only doctor, without calling a model. Job and
supervision cards expose recorded outcomes and explicit control proposals.
No generated unrestricted shell commands are executed.

## Agents and background work

```sh
atbots agents list
atbots agents show researcher
atbots chat researcher "Hello"
atbots agents configure researcher --revision 1 --state paused
atbots jobs submit researcher "Write a report" --start
atbots jobs list
atbots jobs show JOB_ID
atbots jobs cancel JOB_ID
atbots runner
```

Inspect the current revision before editing. Agent states are active/paused/
retired; retirement retains data. Jobs survive the calling terminal, with durable
events/results and one active claim per agent. `replied` is not independently
verified completion. Cancellation or expired leases may require reconciliation;
there is no blind external-effect replay. Local pause/resume applies to queued
jobs; active process pause belongs to AtSys. Questions while busy return labeled
recorded state, not a fabricated live worker reply.

```sh
atbots schedules create researcher "Write a briefing" --cron "0 9 * * mon" --timezone Australia/Sydney --missed skip --overlap skip
atbots schedules preview SCHEDULE_ID
atbots schedules pause SCHEDULE_ID
```

For one-shot work use `--at 2027-01-02T09:00:00+11:00` instead of cron. Offset-free
times are refused. Spring-forward gaps skip; repeated fall-back wall times have
distinct UTC occurrences. Missed runs skip or catch up once; overlaps skip or
queue. Paused agents cannot start new scheduled or previously queued work.
The UI-managed background runner handles local schedules; do not start a second
runner for the same root. Use your OS service manager only for explicit boot setup.

## Models and authentication

```sh
atbots auth login chatgpt
atbots agents create assistant --provider chatgpt --model YOUR_ACCESSIBLE_MODEL --allow-remote
```

Account login is not proof of entitlement. Anthropic uses an API key reference:
`--provider anthropic --model MODEL --api-key-env ANTHROPIC_API_KEY --allow-remote`.
Copilot model access uses `github-copilot`; AtSys coding-CLI selection uses
`copilot`. Compatible APIs use `--provider openai-compatible --endpoint HTTPS_URL
--model MODEL --api-key-env ENV_NAME --allow-remote`. Provision secret values
securely outside prompts/configuration; native credentials stay in their secure
store. No silent paid-provider fallback or subscription proxying.

## Inspectable memory

Each agent has an isolated AtMem database/scope. Chat supports
`remember: I prefer concise technical answers`. Eligible user statements are
also captured by AtMem's deterministic formation rules, not unlimited semantic
extraction. Replies/browser traces are not automatically verified lessons.
Recall records applicable evidence and exposure receipts.

```sh
atbots memory researcher list
atbots memory researcher search "answer preferences"
atbots memory researcher remember "I prefer concise technical answers"
atbots memory researcher correct RECORD_ID "I prefer detailed technical answers"
atbots memory researcher forget RECORD_ID
```

Cross-agent sharing is refused, even if a legacy database contains a sharing
edge. The control-room model sees fleet configuration/status, not private memory,
histories or job bodies. Operator memory inspection stays in the selected agent
view. Own-memory native tools record exposure; model-proposed writes need operator
approval. Known secret patterns are refused, not comprehensive DLP.

## Files, browser and skills

Existing/CLI-created agents' capabilities default off. The New agent form visibly
offers private-workspace read/create checkboxes before approval. Grant only what is needed with
`agents configure NAME --revision N --capabilities JSON`, for example:

```json
{"file_read":true,"file_create":true,"browser_domains":["example.com"],"browser_actions":["navigate","snapshot"],"skills":[]}
```

File tools operate in that agent's workspace `files` directory, refusing escape
and overwrite. This is not an OS sandbox for trusted native extensions. Browser
tools use upstream Playwright with isolated profiles and explicit domains/actions.
The optional `"browser_transport":"mcp"` capability exposes those same governed
tools through the upstream MCP SDK over a local stdio process. The default
`"native"` transport calls Playwright directly. Neither transport grants
additional domains/actions or starts a public MCP listener. The browser extra
installs the MCP dependencies; the web settings form also selects the transport.
Downloads, service workers and WebSockets are disabled. Click/type need grants;
screenshots additionally need vision support and its grant. Provision Chromium
with `python -m playwright install chromium` (Linux may need `--with-deps`), or
reuse existing macOS Chrome.

`atbots browser researcher --url https://example.com` opens headed human takeover;
finish authentication and press Enter. No credential scraping/MFA/CAPTCHA bypass.
Browser-only X/Twitter automation is refused. Browser profiles/keychains are not
exported with agent state. For explicit encrypted session provisioning, use the
operator-only `browser NAME --export-session FILE --key-env ENV_NAME` and
`--import-session FILE --key-env ENV_NAME` options. Provision a Fernet key securely
and transfer that file only to a trusted runtime with identical domain grants.
These operations are not model tools and never print tokens.

Place a skill directory inside the agent's `files` folder, then review and pin it:

```sh
atbots skills researcher review my-skill
atbots skills researcher install research my-skill REVIEWED_SHA256
```

Code files need separate `--allow-code`; installation never executes them. Grant
the installed name in capabilities for on-demand loading. The agent's
`available_skills` tool lists the built-in AtSys guidance plus installed names in its explicit grant, never
other agents' or ungranted bundles. Content is checked
against its approved digest again on load. Remote skill discovery/dependency
installation is not implemented.

## Optional AtSys and AtFlows

AtSys >=0.3.0b4 is version-checked. Worker/supervisor/repair providers and models
are independent (`codex`, `claude`, `copilot`), with explicit effort, validator,
artifacts, stages, plan and deadlines. Claude/Copilot tools need trusted-local
execution permission. AtSys owns supervision and reports, not an AtBots watchdog.
**Start private AtSys** uses this agent's `atsys-state` directory and upstream
setup commands, not a global watchdog restart. Readiness checks inspect the
watchdog protocol/health as well as the dashboard version before consuming the
approval. Startup itself submits no task and calls no model. Private runtime
state is not included in portable backups; set up a new execution owner at the
destination. A saved role profile alone is not a live-service health check.

```sh
atbots supervision list
atbots supervision status DELEGATION_ID
atbots supervision report DELEGATION_ID
atbots supervision stop DELEGATION_ID
```

Pause/resume and non-running objective/plan amendments go to the execution owner.
No upstream live worker-question API is invented. AtSys currently requires
macOS/Linux process support; Windows AtBots does not imply Windows AtSys parity.
The agent can call `supervision_tasks`, read its own durable `supervision_report`,
and propose pause/resume/stop for operator approval. Reports remain readable from
private state after its service stops; this does not prove a worker is still live.
The global installed service can be older than the source repository: upgrade
only after reviewing existing managed work, not automatically during install.

AtFlows observes model calls, tokens/latency and available cost; it is not a
workflow engine. With an existing server, the approved `atflows_connect` operation
can use `http://127.0.0.1:8080/ollama` for compatible local bindings, preserving
egress/credentials. Native subscription OAuth is not redirected through that
proxy. This path does not export task/tool events.

## Portable state and cloud

`atbots export NAME --output definition.json` exports configuration only;
`atbots import definition.json` creates without overwrite. Remote access requires
a new `--allow-remote` grant. Credentials are references, never bundled.

Provision a Fernet key securely in an environment variable. Use
`state export ARCHIVE --name NAME --key-env ENV_NAME`, then
`--root NEW_EMPTY_ROOT state import ARCHIVE --key-env ENV_NAME`. Native history,
AtMem SQLite backups, files, schedules and job/event receipts transfer. Browser
profiles, keychains and cross-agent sharing do not. This backup interface alone
does not transfer ownership safely between two active clones.

Cloud Run Jobs tooling includes wheel-only `image-build --wheel WHEEL --image
REGISTRY_TAG --base DIGEST_PINNED_BASE --approve`, and `cloud plan|stage|deploy|
status|run|logs|stop|destroy|schedule|unschedule|restore --plan PLAN.json`. Mutations need `--approve`; stop
also needs `--execution`. Stage needs `--name` and the provisioned state key.

Plans require project/region/job/image digest/GCS URI/service account/state-key
secret/model-secret references/timeout/spending grant and acknowledgement that
it is **not a provider hard billing cap**. Provision IAM, registry, bucket and
Secret Manager separately. A desktop keychain or local Ollama cannot migrate:
use an explicit remote API binding. Stage requires paused source/no unfinished
jobs, fences source configuration, and activates only the encrypted destination.
Uncertain staging remains fenced for operator reconciliation, not blind replay.
`max_executions` defaults to one (maximum 100); the persisted counter bounds
remote invocations, not dollar charges. Exhaustion requires a newly reviewed plan.

The cloud worker uses an exclusive writer lease and object-generation CAS.
Crashed leases are not automatically stolen. `cloud restore --destination
NEW_EMPTY_ROOT` claims a permanent remote handoff fence, restores a new paused
local owner and leaves credential checking/activation explicit. It never merges
into an existing local store. `schedule` creates an OAuth Cloud Scheduler trigger
from plan cron/timezone; remove it with `unschedule` as part of cleanup, separately
from deleting the Cloud Run job. The API/flags follow Google's
[scheduled jobs guide](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)
and [Scheduler command contract](https://docs.cloud.google.com/sdk/gcloud/reference/scheduler/jobs/create/http).
Do not delete fences to force local resume. Cloud Run is a selected target,
not a guaranteed cheapest provider. Paid cloud acceptance requires its own
specific spending grant; none was used for this implementation pass.

## Doctor, library and compatibility

`atbots --root YOUR_PLATFORM_ROOT doctor` checks registry, disk, extras, workspace
and credential references without revealing values or paid inference. Unchecked
model/cloud permissions stay explicit. Legacy `atbots doctor` checks the old
companion. Default platform root is `~/.atbots/platform`; old config remains.

```python
from atbots.platform import AgentStore
from atbots.platform.session import AgentSession
store = AgentStore("/private/agents")
store.create("researcher")  # once
session = AgentSession(store, "researcher")
print(session.chat("Hello").text)
native_agent = session.agent
```

Native Pydantic AI models/tools/toolsets are accepted directly as trusted caller
code. Calling `native_agent` bypasses AtBots persistence/limits; use session.chat
for that wiring. Explicit restricted input refuses remote inference. Dollar
cost/total-token enforcement depends on provider telemetry, not a billing cap.

Legacy TaskAgent/auth/companion APIs remain; nothing silently migrates or deletes
their data. [Verification](../specs/006-agent-control-room/verification.md) records
actual gates and missing acceptance. Cross-platform CI configuration is not a
claim that those remote jobs have already run. No corrected-UI release has been published.
