# Platform implementation verification — 2026-10-26

Historical record. See [2026-10-27 corrective verification](corrective-verification-20261027.md)
for the current UI-first `0.3.0b2.dev0` candidate, strict memory walls, user-app
uninstall and live Copilot memory/file/tool acceptance. The version/publication
statements below describe their dated runs, not today's source state.

Branch `006-agent-control-room`. Unreleased source candidate, version unchanged
at 0.2.0. Nothing tagged, pushed, published or deployed to paid infrastructure.
No existing installed user AtBots/AtSys service was replaced. Tests use a separate
pip environment `/tmp/atbots-auth-oEWbti/venv` on macOS/Python 3.12.2.

## Implemented paths

Persistent named agents, stable-ID private workspaces and native Pydantic AI
history/Agent access; local and explicit remote provider bindings; typed terminal
and web management; durable approval/revision guards; AtMem recall/exposure,
deterministic eligible user capture, inspect/correct/forget/directional sharing;
detached jobs/events/cancellation/leases and no blind uncertain replay; persisted
one-shot/cron schedules, edit/preview/policies and DST behavior; approved-root
files, upstream Playwright browser tools, native images, human takeover and
operator-only encrypted session provisioning; reviewed digest-pinned local skills;
AtSys submit/correlation/status/report/actions/amendment and independent role
bindings; compatible-provider AtFlows tracing; portable encrypted state, wheel-only
container build, pinned Cloud Run plans, GCS ownership/CAS, handoff/restore fences,
bounded remote execution counts and explicit Cloud Scheduler commands; loopback
web client, doctor and guides. No new inference loop or duplicate supervisor.

## Deterministic and installed-package gates

Source suite before the final concurrency tightening: **212 passed, 6 opt-in
live evals deselected**. Included all 41 feature-005 authentication tests. Focused
installed-wheel suite outside the repository: **145 passed**; those are a subset,
not 145 additional distinct scenarios. Final recheck/artifact identifiers appear
below. Ruff on new modules/tests/smoke scripts, build wheel/sdist, `pip check` and
`git diff --check` pass. `evals/baseline.json` remains the preexisting user edit.

Final recheck after snapshot/job/handoff locking and fleet-reference context:
**212 passed, 6 deselected in 35.25s**. Final rebuilt/installed wheel, tested from
an isolated copied test directory without source pythonpath or repository pytest
configuration: **145 passed in 35.95s**, no warnings. Artifact:
`/tmp/atbots-auth-oEWbti/platform-delivery/atbots-0.2.0-py3-none-any.whl`.
SHA-256 `72234dfed30f2bb3fe784b8699dd68f1c0db4cf0dcea61b24531d6a6b1ebb1b9`.
This 0.2.0 version is a local candidate only and must not overwrite the published
0.2.0. A release needs a new explicit version and independent publication gates.

`evals/platform-intents-v1.json` contains 19 authored intent cases, with native
typed-contract/no-unapproved-mutation tests. These fixtures verify wiring, not
live routing accuracy or general prompt-injection immunity. Cross-platform CI
matrix is configured; no remote CI success or Windows/Linux qualification is
claimed merely from its presence.

## Real local and browser acceptance

`scripts/smoke_platform.py` used the installed wheel, existing local Ollama
`qwen3:4b-atbots-ctx8192`, no model download or paid API. An independently launched
worker persisted a `replied` result, and the real control-room model proposed and
approved agent creation. Preserved evidence root:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-platform-acceptance-bxa4uqd7`.
Job `6e0fbb39f1b1476a82398f084f6fc6e7`. The script checks its narrow expected
response; job receipts still do not promote arbitrary objectives to verified.

The same smoke started an isolated AtFlows source server with temporary data and
ports. A genuine proxied local model call was persisted as one trace, with 39
input tokens and 1,473 output tokens. These are that smoke's telemetry, not a
performance benchmark. Owned service was stopped; existing services untouched.

Real isolated Chrome fixture tests exercised navigation, text entry, click,
accessibility snapshot, native PNG payload and encrypted fixture-session transfer.
Web tests check authentication, Host/Origin refusal, approval/reload/single-use,
artifact scope, native list chat, browser approval/application and desktop/mobile
layout. Screenshots were inspected; low-contrast agent buttons and raw JSON list
replies were corrected. No personal browser profile was accessed. Real vision-
model interpretation/site-specific production authentication remain unqualified.

## AtSys actual runtime, fixture providers

Installed AtSys 0.3.0b4 was launched with isolated data/ports and **upstream CLI
fixtures**, not paid providers. Adapter submitted a real task; first attempt
failed, observer opened an incident, Claude-shaped supervisor proposed repair,
Codex-shaped repair ran, Copilot-shaped worker retried, independent file validator
passed and durable report was retrieved. AtSys remained the execution owner.

Task `task-f62b4e28-1ecf-459b-96ee-3312b6d6c3b6`, status completed; five recorded
attempt records include role/validation activity, not five failed worker retries.
Events include `incident.opened`, `proposal.received`, `repair.authorized`,
`retry.authorized`, `task.completed`, `report.generated`. Evidence:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-supervision-acceptance-jctz2cci`.
Reproduce using `scripts/smoke_supervision.py --atsys-source PATH`.

This establishes installed transport, ownership, mixed-role protocol and recovery
plumbing. It is **not live LLM worker/supervisor/repair qualification**. Global
AtSys remains 0.3.0b2; it was not upgraded over existing work. Upstream source
at `c19ab97e80714981b5b146e7efc238a7cdfa32b6` independently records short live
provider checks; those do not substitute for AtBots' SC-010 campaign.

## Cloud safety tests, not live deployment

Tests cover config/remote grants, encrypted state/memory/event roundtrip,
no browser/keychain inclusion, digest-pinned static argv, create-only state/lease
claims, source fence, new paused local restore, execution allowance, checkpoint
CAS failure retaining ownership and OAuth Scheduler target/no retry. IAM, image
build/push, deployment, scheduled run/artifact, restart and bill/cleanup still
need a live authorized cloud acceptance. No project/spending grant was invented
from unrelated benchmark budgets. The repository environment file is ignored,
never bundled; credential presence was checked without displaying values.

## Open gates — not product complete

- T006: planned browser-MCP deployment/CLI surface versus direct upstream
  Playwright implementation needs alignment/qualification; real vision-model and
  legitimate site-auth acceptance remains. Local reviewed bundles are implemented,
  not an autonomous remote skill marketplace/dependency installer.
- T008/SC-006/010: real role-provider/mixed-runtime qualification was completed
  in the follow-up below. No invented live-question/model-observer API.
- T009/SC-007: authorized paid cloud end-to-end and exact resource/charge/cleanup
  receipts; existing local-store merge remains unsupported by design.
- T010: expanded browser walkthrough for work/progress/memory/artifact/deployment
  families beyond the currently checked list/create/approve/memory/files/artifact
  and API tests; the web client now has direct Memory/Files inspection controls.
- T011: Windows/Linux installed execution and full live intent-quality evaluation.
- Constitutional legacy retirement/migration conflict: inventory is in
  `docs/platform-compatibility.md`; legacy APIs preserved, not quietly removed or
  certified compliant. No removal has been performed.

Known-pattern screening is not comprehensive DLP. Native caller-supplied code is
trusted, not sandboxed by workspace directories. Subscription access is not a
cloud entitlement. Monetary prices remain unknown; invocation/token/time limits
are not a provider billing cap. No overall completed/release-ready claim.

## SpecKit convergence

Checked 40 functional requirements, ten success-criteria gates, the feature's
eight user-story scopes, nine delivery slices and seven governing principles plus
public-surface/migration rules. Seven findings appended as T012–T018: one critical
legacy-retirement contradiction, five high partial acceptance/integration gaps,
one medium live-intent-quality gap. These do not replace or erase unchecked
T006/T008/T009/T010/T011. No scope reduction or feature removal was inferred.
Optional Git hooks were not run; unrelated dirty work was preserved.

## Non-deployment follow-up — 2026-10-26

The user excluded deployment from this pass. T009/T015 live cloud acceptance
therefore remain deferred, not satisfied or removed from the specification.

Implemented optional governed stdio MCP browser transport using MCP SDK 2.3,
Pydantic AI's native MCPToolset and upstream FastMCP client transport. Real
subprocess/browser acceptance passed native PNG output, exact tool grants and
denied domains. Granted installed skills now have a discovery tool. No public
MCP endpoint, credential inheritance or unrestricted browser server was added.

Real AtSys 0.3.0b4 qualification completed **three real CLI worker tasks**, each
with independent validation and a durable report, through the AtBots adapter:

| Worker | Task | Result |
| --- | --- | --- |
| Codex | `task-3f897ccb-888e-44bc-a9ca-e2c9c1d372e8` | Completed; controlled validator failure, Claude supervisor, Copilot repair, Codex retry, validator passed |
| Claude | `task-89a97cd0-3866-4288-8b4c-c9402b34a9ba` | Completed with report |
| Copilot | `task-7f975ad0-ed50-4025-965f-ba020e39f26c` | Completed with report |

Evidence: `/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-live-supervision-2ktd6h7m/summary.json`.
Versions: codex-cli 0.163.0, Claude Code 2.1.281, Copilot CLI 1.0.103.
CLI-configured default models were used; no exact backend model is inferred
from a provider name. Isolated service/daemon stopped after qualification;
global installation and managed work were not replaced. Reproduce with
`scripts/qualify_supervision.py` using the already authenticated CLIs.

The web client now serves packaged JS/CSS with a self-only CSP, no inline-script
exception. New-agent/settings forms produce typed durable approval proposals;
job/schedule/supervision controls use the same boundary. Setup doctor is
authenticated and read-only. Memory content is shown separately from expandable
authority receipts. Agent-scoped file buttons retain the selected scope even
if fleet selection changes. Additional browser tests cover form creation,
approval, rejected reconfiguration and unchanged stored instructions.

macOS source gate: **216 passed, 6 opt-in evals deselected**. Focused follow-up
web/control/intent contract tests: **38 passed**. These counts overlap.
Desktop/mobile screenshots were inspected and memory display simplified.

First Windows installed-wheel gate: **212 passed, 2 skipped, 6 deselected** on
Python 3.12.6. First WSL Ubuntu gate: **211 passed, 1 skipped, 2 failed**;
both failures were missing Chromium shared libraries (`libnspr4.so`). The host
setup is being repaired and the newer UI wheel requalified; these initial
results are not certification of the latest source.
Initial remote evidence:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-remote-evidence-8lkfdmt_`.
Qualification now uses a uniquely named `/var/tmp` environment, since WSL clears
`/tmp` when the distro stops. An explicit `--linux-install-deps` option installs
the upstream Playwright OS prerequisites; no existing Python environment changes.

Bounded OpenAI vision/intent acceptance remains blocked: metadata-only
authentication checks returned **401 invalid_api_key** for the configured
`OPENAI_API_KEY` in both known project env files, including after the user
reported an update. No key value or raw provider response was recorded. The
exact updated file path has been requested. Local-model intent quality is being
measured separately; scripted contract tests are not counted as live accuracy.

The user clarified the env location is the `aetnamem` repository; the subsequent
metadata-only authentication retry of that exact file also returned 401.
The original local Qwen3:4b intent run scored **7/19**, with **11 timeouts** and
one incorrect plan. Evidence:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-nondeploy-live-214w4xtw/summary.json`.
The qualification script's output-token bound was not reaching the control-room
session; explicit native model-settings forwarding fixes that wiring, covered
by a new regression test (**21 intent contract tests passed**). A subsequent
three-case token-bounded smoke passed 3/3; it is not a replacement 19-case score.
An explicit reasoning-effort option supports testing Ollama's documented
`none` setting without changing user agent defaults. The original failed run is
preserved, not replaced by the smoke.

Legacy retirement T012 is still unfinished. No legacy code/config/data was
deleted in this follow-up. This remains an unreleased, incomplete source
candidate, not a completed platform or release claim.

### Latest qualification delta

Stage-2 wheel SHA-256:
`c5d10ac16509687abd2b35b0b2442f2da8fb924d917da7dfd3bb3018a65f47ae`.
Windows installed suite: **214 passed, 2 skipped, 6 deselected**. After installing
the upstream OS prerequisites, WSL Ubuntu passed the MCP/browser transport test,
but its full suite still had **213 passed, 1 skipped, 2 failed**: both web
walkthroughs timed out on browser button actionability. Evidence:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-remote-evidence-atuvu7lt`.
Full Chromium rather than headless-shell is being checked independently;
no force-click, disabled assertion or skipped UI gate was substituted.

A subsequent macOS full suite had **216 passed, 1 failed, 6 deselected**: the
settings test's five-second proposal wait expired under concurrent local model
load. The form now shows pending feedback and prevents duplicate submissions;
the UI test allows a bounded 20-second proposal wait. Focused web suite after
this change: **8 passed**. This is not a fresh full-suite pass. Latest intent
contract suite: **22 passed**.

The live-intent fixture also precreated `researcher` before asking to create it.
Fixture version 2 explicitly omits that target for the creation case; a regression
assertion prevents this contradiction. Prior scores are retained with their
original setup, not presented as clean version-2 results. No broad live-intent
quality or final cross-platform readiness claim is made yet.

## API credential and live qualification — 2026-10-27

The user supplied a replacement credential for these bounded checks. Direct
OpenAI model-metadata authentication succeeded, followed by a native AtBots
session reply (one request, 28 input tokens, 5 output tokens). The credential was
provided through a hidden terminal prompt and retained only in process memory;
it was not saved to project env files, source, configuration or evidence.
The earlier authentication blocker is therefore cleared for these checks, not
evidence that either project's existing env credential was updated.

Real browser/vision acceptance with `gpt-5.4-nano` passed **both transports**:

| Transport | Result | Model requests |
| --- | --- | ---: |
| Direct Playwright/native tools | Screen-rendered random code read correctly | 3 |
| Governed stdio MCP tools | Screen-rendered random code read correctly | 3 |

Evidence:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-nondeploy-live-e6c6a7sk/summary.json`.
The initial vision call failed because this model's Chat Completions endpoint
rejects reasoning-enabled function tools. Qualification now explicitly uses
`reasoning_effort=none` for vision; it does not change any persisted agent default
or add a fallback execution loop. Failed attempts remain in their original roots.

The separate version-2, real-model intent campaign scored **17/19**. One case
routed background-work inspection to agent configuration inspection; another
failed structured output validation. No proposals were approved, no cloud
resources were created, and no unauthorized mutations occurred. This is a
measured routing result, not universal intent or injection-safety qualification.
Recorded successful-turn usage totals: 51,401 input and 2,337 output tokens;
failed-turn usage is unavailable, so these are not complete campaign billing
totals or a measured dollar cost.
Evidence:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-nondeploy-live-956_fu57/summary.json`.

The second local Qwen3:4b campaign (`reasoning_effort=none`) scored **5/19**
under the earlier fixture setup. It remains preserved separately at
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-nondeploy-live-0ds3x72z/summary.json`.
Do not replace this result with the three-case smoke or claim local routing
parity with the API model. The additional WSL full-Chromium UI attempt exceeded
its 300-second runner timeout; Linux UI acceptance remains open, not passed.

No deployment, publication, commit or push was performed. Legacy migration,
full UI/cross-platform closure and the remaining intent failures are still open.
