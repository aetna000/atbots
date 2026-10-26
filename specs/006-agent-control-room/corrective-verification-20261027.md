# UI-first corrective delivery — 2026-10-27

Candidate: `0.3.0b2.dev0`, branch `006-agent-control-room`. Unpublished.
This record supersedes the sharing/setup behavior in the older 0.3.0b1 beta;
the dated earlier verification remains historical evidence, not current policy.

## Delivered journey

1. `atbots` opens the UI and starts/reconnects to one private local desktop/runner.
   Terminal management remains available with `atbots control`.
2. Setup connects reusable supported ChatGPT/Copilot account profiles or
   OpenAI/Anthropic API credentials. API credentials use the approved OS keychain;
   configuration/database/UI responses contain references, not key values.
3. Control-room model switching and agent creation are typed forms, independent
   of the current model's availability. Provider catalogs supply model IDs;
   opening Settings cannot silently change an unlisted existing model.
4. Each ordinary agent has a private workspace, AtMem and callable own-memory
   tools, environment identity and built-in AtSys skill. The control-room model
   receives fleet metadata, not private memory, history or job bodies.
5. Native tools propose memory writes, schedules and supervised objectives for
   operator approval. Proposed work is never called started. Scoped supervision
   stores separate CLI/model/validator/permission choices and real upstream IDs.
6. The UI exposes memory search/remember/correct/forget, files, workspace path,
   AtSys settings, one-time scheduling, AtFlows proxy configuration, component
   versions, and pause/archive/restore. Archiving retains data. Conversation
   messages survive page reload; drafts and late responses stay in their agent
   view. Approval cards have readable summaries with expandable exact receipts.
7. Component maintenance is allowlisted and confirmed, requires quiescence,
   checks installed compatibility pins and delegated-work status, and requires
   restart. It stops only verified, idle private AtSys processes before pip runs;
   active tasks and unverified process identities block maintenance. Reports and
   private state are retained. No actual package upgrade was tested against a
   user environment.
8. Closing the tab/launching terminal does not stop schedules. Paused agents
   cannot launch previously queued work. Transient runner setup failures get
   three bounded retries; stale/blocked status is visible and uncertain work
   is not automatically replayed. No idle inference loop was added.

## Executed checks

Final source suite: **253 passed, 6 opt-in evals deselected**, 131.08 seconds,
macOS/Python 3.12.2. JUnit: `/tmp/atbots-corrected-ui-source-final-20261027.xml`.
Focused environment/private-service/component gate before the last own-task
report test: **14 passed**. That additional test is included in the full gate.
Selected corrective files pass Ruff F/I/B/SIM; JavaScript syntax and
`git diff --check` pass. This is not a claim that all legacy scripts are lint-clean.

The clean pip environment is `/tmp/atbots-corrected-ui-install-20261027`.
The candidate wheel and sdist are in `/tmp/atbots-corrected-ui-20261027`.
Installation is temporary qualification, not a reinstall into the user's apps.
`pip check` passed. Assets and `atsys-skill.md` are included in the wheel.
The installed module resolves to that environment's `site-packages`, not the
source tree; its CLI and package metadata both report `0.3.0b2.dev0`.
Final clean-installed gate: **181 passed**, 131.28 seconds, from `/tmp` with
`PYTHONPATH` removed and repository pytest configuration disabled. JUnit:
`/tmp/atbots-corrected-ui-installed-final-20261027.xml`. The first collection
attempt lacked the repository-owned intent fixture; after copying that fixture
alongside the copied tests, the complete gate passed. No application fix or
source-tree import was used to mask that harness setup error.

Browser checks exercise real Chrome at 1440×1000 and 390×844. Provider/API-key
setup in these browser tests uses test doubles: it proves UI plumbing and secret
boundaries, not new account consent or API entitlement. The walkthrough covers
connect → model switch → approval → new agent → environment → scoped supervision
→ components, plus preserving an existing model absent from the current catalog.
Browser console errors are asserted absent; mobile horizontal overflow is checked.
Screenshots were visually inspected and copied to
`/tmp/atbots-corrected-ui-20261027/journey-desktop.png` and `journey-mobile.png`.

Native integration checks separately use real temporary SQLite/AtMem stores.
Tests include legacy-sharing-edge rejection, private memory canaries, replacement
memory ports, explicit write approval, stale forms/record approvals, paused-job
launch rejection, scoped state export and runner startup/reconnection/recovery.

## Live inference (not scripted model responses)

Your existing AtBots GitHub Copilot profile was reused through the supported
provider adapter. No pasted API credential or another application's token files
were used, and no existing agent was reconfigured.

| Check | Actual result |
| --- | --- |
| Provider catalog | Returned accessible model IDs; catalog access not counted as inference |
| `gpt-4o-mini`: environment | 2 model requests; real `inspect_environment` return; correct workspace, AtMem 2.3.10, built-in AtSys, and unconfigured supervision reported |
| `gpt-4o-mini`: memory/files/skill | 2 model requests; real `search_memory`, `create_file`, `available_skills`, `load_atsys_skill` returns |
| File assertion | `acceptance.txt` existed with exact content `AtBots workspace verified` |
| Memory assertion | Own preference returned with AtMem exposure receipt; other agent's canary absent; no extra memory was stored |

Local Qwen results are not hidden: a Qwen3:4b call exceeded a 90-second bound,
and the 8192-context variant exceeded a 120-second bound. A smaller Qwen variant
returned the right path/backend but gave a misleading tool-access explanation;
that is not counted as successful tool-use acceptance. The Copilot checks above
verified actual tool returns rather than trusting the assistant's narration.
No default provider fallback or automatic replay was added to conceal these cases.

## Real supervised task and durable report

Isolated qualification root:
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-supervision-corrective-1cb0z8hc`.
This is a temporary local evidence location, not a permanent remote archive.

The real Copilot agent proposed an objective through its native tool. After
operator approval, upstream AtSys used a real Codex worker and independently
validated the artifact. The successful task is
`task-76c433d8-a56d-4acc-9079-fb12af611134`; status `completed`,
`workflowAccepted: true`. Report digest:
`cb4a84681c9d71de381f0a422dbc7d28ae9ca6fe38602d09408f6c30f760534a`.
Artifact `supervised.txt` contains exactly `SUPERVISED_READY`; SHA-256:
`92297af72e4e90b5d5ed88aa39d7e9b0a5cfdffc34b5c0b401850481801d6feb`.

Setup failures were retained, not counted as successes. The existing shared
watchdog lacked the multi-provider protocol; it was not restarted or modified.
The first private task (`task-a6ed94c4-92a0-4791-83cf-93a5c6eb637f`) hit Codex's
untrusted/non-Git workspace check and ended `needs_attention`. The UI now offers
explicit workspace-only Git initialization and checks readiness before consuming
an approval. No trust-check bypass was added.

Real private startup → readiness → verified idle shutdown → repeated shutdown
was also checked. Both reports survived shutdown and native offline reads.
No qualification watchdog/dashboard remains running. Agent-native report/control
tools reject other agents' task IDs before upstream access. Copilot's first
read-only report attempt dropped the `task-` prefix and correctly got `not_found`;
one explicit retry returned the actual durable report and digest in two model
requests, without starting a service or replaying a task.

## Browser MCP cold-start correction

Discovery now lists upstream tools without launching Chrome; the first granted
tool opens one lazily managed browser lifetime, closed on disconnect. The native
tool-call read allowance is 90 seconds, separately from initialization; the
enclosing session deadline still bounds the turn. No silent model replay.

An earlier production-session series was **4/5**, including a cold timeout at
42.58 seconds; this failure is not erased. After the bounded allowance change,
`scripts/qualify_mcp_stability.py --runs 5` passed **5/5** with elapsed times
7.73, 6.93, 6.93, 6.96 and 7.04 seconds. Its retained local stores are under
`/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atbots-mcp-stability-555spqat`.
These checks use the real production session, MCP transport, Chrome and image
payloads, but a scripted FunctionModel: they establish transport/lifetime behavior,
not real vision-model interpretation or a universal startup-latency guarantee.

## Preservation and remaining gates

The old app was explicitly uninstalled from both user-facing pip environments:
`/Users/javadtaghia/miniconda3` and `/Users/javadtaghia/.venvs/atbots`.
Existing `~/.atbots` data, memory, credentials, workspaces and other dependencies
were retained. The user's unrelated `evals/baseline.json` edit was preserved.

This correction is not a new public release. Nothing was tagged, pushed,
deployed or reinstalled into those user-facing environments. Cloud acceptance
remains deferred. Fresh Windows/Linux qualification, legacy API migration and
the wider live-provider/intent matrix remain separate open tasks. AtSys native
execution still requires a supported host/service and authenticated coding CLI;
installing its package or saving a profile is not service-health proof.

Unsupported Anthropic subscription OAuth is not advertised. AtFlows tracing
needs a real configured service; a proxy endpoint is not proof of trace delivery.
The UI does not promise OS boot auto-start, permanent data deletion, a security
sandbox for trusted CLI code, or uninterrupted operation while the PC is asleep.

## Artifact identities

- Wheel SHA-256: `bdcd38537772b30e6e0dfff2f54c425db9ee46e65bee833a2c046cd3075406ec`
- Sdist SHA-256: `4a4d8017020209ec6d5747e207b3b1d7145949e4694de91fa8f808f4d9dd8282`
