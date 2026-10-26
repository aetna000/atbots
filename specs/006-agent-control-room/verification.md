# Foundation implementation verification — 2026-10-26

Branch: `006-agent-control-room`. Package version unchanged at 0.2.0; this is an
unreleased source candidate, not a replacement for the published artifact.

## Implemented and checked

T001–T003: strict agent definitions and model references, isolated stable-ID
workspaces, private SQLite registry/native histories, revisions and turn locks;
native Pydantic AI sessions with exposed Agent/tools/toolsets, request/token
accounting and timeout; named CLI and typed conversational management, with
explicit remote grants and expiring single-use in-process mutation approvals.

T004 partial: default AtMem port, explicit user-authorized `remember:` capture,
applicable context, real exposure receipts, distinct per-agent databases/scopes,
and refusal of recognizable credential patterns before ordinary input capture.
No agent output is automatically promoted to a verified lesson.

Source suite: **155 passed, 6 opt-in live-model tests deselected**, macOS/Python
3.12.2 in isolated pip environment `/tmp/atbots-auth-oEWbti/venv`. Includes all 41
feature-005 authentication tests and 47 new platform tests, plus the new core
dependency's metadata check. New platform/auth
modules and tests pass Ruff; `git diff --check` passes. No global Python upgrade.

Build produced wheel/sdist under `/tmp/atbots-auth-oEWbti/platform-dist`.
An earlier installed-wheel pass ran 86 focused auth/platform tests successfully
outside the repository with no source pythonpath. The final rebuilt artifact
includes the subsequent control-prompt and credential-instruction regressions;
its result is recorded below. Installed tests are subsets of the source suite,
not extra distinct scenarios. `pip check` passes.

## Real local-model checks (not benchmarks)

Used existing Ollama `qwen3:4b-atbots-ctx8192` on numeric loopback; no model
download, paid API call, cloud resource or external notification. Local native
conversation returned READY in one request and persisted revision 1.
Evidence root:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-platform-live-xzujcn6w`.

The first real control-room create check failed: the model incorrectly treated
implemented creation as unsupported because management instructions mixed it
with negative statements about unfinished deployment features. This failed
probe is not counted as a success. Its isolated root is
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-control-live-iu28en_o`.

Correction: supply explicit available operation meanings and pass registry
metadata only, never other agents' instruction bodies. Added a regression for
that information boundary. A fresh local check then proposed create/researcher,
verified no mutation before approval, applied the exact approved creation, and
proposed list on the follow-up. Root:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-control-live-v2-o7u84zre`.
These are narrow smoke results, not a routing-accuracy estimate or proof of
universal prompt-injection safety. Temporary roots contain real local app state;
they were not deleted or merged into any existing user workspace.

## Dependencies and scope correction

AtSys inspected local/remote main at c19ab97e80714981b5b146e7efc238a7cdfa32b6.
Existing feature 008-provider-parity and release 0.3.0b4 provide codex/claude/
copilot roles. Its records include 99 backend and 20 browser tests plus real
short workers. AtBots integration still requires its own T008 acceptance. No
AtSys source or running service was modified. Do not confuse native process
pause with session resume or fixture recovery tests with live failure recovery.

AtFlows is observability, not a procedure executor. The feature specification
and plan now reflect its real compatible-proxy/telemetry integration. No AtFlows
source/service was changed.

## Not complete / not claimed

T004 remaining memory controls; T005 durable jobs/approvals/background questions;
T006 browser/vision/files/skills; T007 scheduler; T008 live integrations;
T009 cloud; T010 web; T011 full acceptance/docs/migration remain pending.
No features removed, release/tag/push performed or desktop keychains exported.
The preexisting user change to evals/baseline.json is preserved.

Known-pattern screening is not comprehensive DLP. Caller-supplied native tools
are trusted executable code, not sandboxed. Native token limits depend on model
usage reporting and are not a hard billing cap. Dollar cost stays unknown. A
successful chat receipt says replied, never objective verified. In-process
control approvals are not durable task approvals. Concurrent questions to a busy
agent currently get a busy error; noninterrupting background questions need T005.
Windows/Linux runtime acceptance and live subscription-provider tests have not
been run for this platform foundation. The source test suite excludes live evals.

## Final installed artifact

Final wheel SHA-256:
`1179df9eb2cc1ac12668024e783e7f52f86b6cfdf093fffd911274a1f110e087`.
Built wheel/sdist, force-installed the wheel into the isolated pip environment,
and ran from `/tmp` without repository pytest config or source pythonpath:
**88 focused tests passed** (47 platform + 41 authentication). An isolated
`python -I` check confirmed `site-packages` imports and successful installed CLI
create/list operations. `pip check` passed. No installed user AtBots/AtSys
runtime was replaced. No Windows/Linux or paid-cloud acceptance is implied.
