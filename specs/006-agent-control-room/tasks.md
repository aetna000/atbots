# Tasks — full platform

## Phase 1: Persistent agent foundation

### Owner-prioritized corrective work (2026-10-27)

- [x] T019 Implement strict per-agent memory walls, scoped callable native memory tools, explicit-write/approval safety and environment awareness; remove private bodies from control-room model inputs; test persisted-sharing rejection, private canaries and memory-port replacement.
- [x] T020 Implement reusable provider connections and safe model discovery plus browser-based supported login/API setup; never expose tokens in definitions, catalogs or logs; preserve existing auth profiles and local defaults.
- [x] T021 Implement UI-first setup/model switching and short agent-creation journey, selected-agent environment/memory/files and per-agent supervision settings; no raw JSON or functioning current model needed for setup. Persist conversation views and isolate drafts/late responses by agent; show readable approval summaries.
- [x] T022 Verify full corrective source/installed/browser journeys and record superseded behavior, remaining blockers and exact evidence. Do not reinstall on the user's machine or publish until separately requested. Evidence: corrective-verification-20261027.md; 253 source / 181 installed tests, real Chrome desktop/mobile walkthrough, exact candidate hashes and retained failure findings.
- [x] T023 Finish agent-private AtSys service setup and explicit workspace Git initialization in the UI, dashboard/watchdog readiness before approval consumption, runtime-state backup exclusion, and a real agent-proposal → approved task → independently validated artifact check. Preserve the failed shared-watchdog and uninitialized-workspace findings. Add own-task durable reports and approval-bound controls; verify idle private shutdown before component maintenance without touching shared services.
- [x] T024 Separate browser MCP discovery from Chrome cold startup using lazy upstream tool lifetimes; test no-launch discovery, single initialization, cleanup and real scoped browser/image transport without suppressing failures. Evidence: production-session 5/5 after the recorded 4/5 cold-start finding; no paid vision inference implied.

Corrective evidence for T019–T024 is scoped to the macOS UI-first delivery.
The older full-platform acceptance tasks below remain open; these checks are not
certification of fresh OAuth consent, all live providers, cloud or Windows/Linux.

- [x] [T001] Implement strict agent/provider/limit contracts and private SQLite registry, stable-ID workspaces, validation, revisions and isolated history in `src/atbots/platform/models.py`, `store.py`; add `tests/test_platform_store.py` (FR-002/003/006/009). Evidence: 23 deterministic tests passed on macOS/Python 3.12.
- [x] [T002] Implement native Pydantic AI sessions with exposed Agent, configured model selection, native history, bounded usage/time, per-conversation serialization and safe failure reporting in `platform/session.py`; reuse auth model construction and test real native Agent with TestModel/FunctionModel (FR-005/006/009/012/017). Evidence: native tool/history/limit tests and real local Ollama reply; vision acceptance belongs to T006.
- [x] [T003] Implement terminal create/list/inspect/configure/chat and interactive control room with schema-validated conversational intents and explicit remote grants in `platform/cli.py`, `control.py`, root `cli.py`; test dispatch, clarification, model selection and no silent fallback (FR-001/004/007/008/011). Evidence: deterministic dispatch/approval tests plus real local-model create/list smoke. Durable approvals and fleet background state remain T005.

## Phase 2: Memory and durable execution

- [x] [T004] Implement AtMem memory port, applicable recall/exposure, eligible capture, inspect/correct/forget/share and secret-filtering boundaries in `platform/memory.py`; real AtMem and substitute-backend tests (FR-013/014/015, SC-003). Implemented native authority operations, rules-based user capture, approved control-room mutations and directional revocable sharing; real-backend tests pass. Automatic formation is limited to AtMem's deterministic extraction coverage, not a claim of multilingual semantic completeness.

  Evidence: ten real memory/control tests plus substitute-port, privacy and native
  session regression coverage. Sharing is read-only, non-transitive and bounded
  to three shared sources per recall; revocation cannot undo prior exposure.

  Superseded policy: the sharing implementation described in this historical
  completion note is disabled by T019 and the 2026-10-27 owner correction.
  New sharing is refused and legacy edges are ignored for future recall.
- [x] [T005] Implement durable jobs/events, background execution, questions while busy, approval lifecycle, cancellation, leases and side-effect reconciliation in `platform/jobs.py`; fault and concurrency tests (FR-010/011/012/020/021/023/035). Evidence: durable single-use approvals, atomic per-agent claims, fenced stale results, no blind replay, cancellation and installed detached local-model worker acceptance. Busy answers are recorded state, not live steering; replied is not verified completion.
- [ ] [T006] Implement upstream browser MCP/vision, approved-root file tools, browser takeover, domain/action permissions and reviewed skill management in `platform/browser.py`, `skills.py`; real local browser fixture acceptance (FR-016/017/018/019, SC-004).
- [x] [T007] Implement persisted scheduling, timezone/DST, overlap, missed-run policies, previews and runner lifecycle in `platform/scheduler.py`; deterministic clock/restart tests (FR-022/023, SC-005). Evidence: one-shot/cron persistence, edit/preview/pause/resume/delete, restart idempotency, overlap/missed policies and DST gap/fold tests; foreground durable runner provided. OS boot integration uses the user's service manager, not an included service installer.

## Phase 3: Integrations and deployment

- [x] [T008] Implement optional AtSys 0.3.0b4 adapter with role providers/models and trusted-local grants, plus AtFlows compatible tracing/telemetry in `platform/integrations/`; verify live task/report and tracing paths, fault recovery and explicit unsupported capabilities (FR-024/025/026/027/038/039/040, SC-006/010). Real Codex/Claude/Copilot CLI workers completed with reports; mixed Codex worker, Claude supervisor and Copilot repair recovered a controlled file fault. AtFlows real local-model trace and deterministic cancellation/unavailable-provider tests remain separate evidence. See verification.md.
- [ ] [T009] Implement portable export/import/move and Cloud Run Jobs deploy/plan/status/logs/stop/destroy, pinned container, external state and cloud secrets in `platform/deployment/`; isolated cloud acceptance under an explicit spending grant (FR-028/029/030/031/032, SC-007).
- [ ] [T010] Implement authenticated first-party web control room on shared operations/events; browser checks for conversation, permissions, artifacts and deployment at desktop/mobile sizes (FR-033, SC-008).

## Phase 4: Full acceptance and packaging

- [ ] [T011] Finish doctor/preflight, legacy migration/removal notices, intent evals, pip extras/guides, installed-wheel and macOS/Windows/Linux acceptance; record blockers and run convergence in `docs/`, `tests/`, `specs/006-agent-control-room/verification.md` (FR-034/036/037, SC-001/002/009).

## Phase 5: Convergence

- [ ] T012 CRITICAL Resolve and implement the legacy-retirement migration against Constitution II/Public Surface and FR-036; use `docs/platform-compatibility.md` to name impacted consumers, provide replacements/notices and acceptance before removing companion/extraction/ranking/custom-loop surfaces. Retention is not certified constitutional compliance (contradicts).
- [ ] T013 Finish T006's upstream browser-MCP deployment/configuration parity or explicitly approve an equivalent upstream Playwright plan alignment; expose discoverable granted skills to the native agent and qualify a real vision model plus legitimate authentication/session transfer per FR-016/017/018/019 and SC-004. Current isolated Chrome/native-image/encrypted-fixture tests are not live vision or MCP acceptance (partial).
- [ ] T014 Complete AtBots-specific live Codex/Claude/Copilot and mixed-runtime role matrix, unavailable-provider/cancellation cases and bounded recovery acceptance per FR-025/026/038/039/040, SC-006/010. Preserve the successful real-runtime fixture recovery separately; obtain applicable trusted-local grants and preserve existing global AtSys managed work (partial).
- [ ] T015 Run an explicitly project/budget-authorized Cloud Run build/push/deploy/schedule/run/artifact/restart/restore/stop/unschedule/destroy acceptance and archive exact image/resource/charge/cleanup receipts per FR-028/029/030/031/032 and SC-007. Never reuse unrelated benchmark spending grants; local safety/CAS/fencing tests do not close this gate (partial).
- [ ] T016 Extend the real-browser control-room walkthrough to chat-based create/configure/work, queued/running/stale/verified-result distinctions, job actions, supervision and deployment permissions per FR-007/008/010/033/035 and SC-008. Existing browser list/create-approval/memory/files/artifact checks and API auth tests remain passing subsets (partial).
- [ ] T017 Execute the configured macOS/Windows/Linux installed-package matrix and dependency-floor/browser checks per FR-037, SC-001/009; fix actual failures and record host/runtime versions. Preserve the unsupported Windows AtSys execution boundary rather than infer provider parity from package installation (partial).
- [ ] T018 Run and report a bounded live-model intent-quality evaluation across operation families, ambiguity and untrusted input per SC-002; preserve 19 authored contract fixtures separately, compare expected operations/targets/grants and correct failures without claiming scripted-model tests establish routing accuracy (partial).

## Phase 6: Convergence

Assessment after T019–T024: the macOS UI-first correction passes its source,
installed-artifact, real Copilot/native-tool and private AtSys acceptance gates.
The following full-platform gaps remain. These are closure criteria for the
existing T012–T018 work, not authorization to publish, provision cloud resources
or remove user data. Findings: one contradicts, five partial; one critical,
four high, one medium. No missing or unrequested finding was added.

- [ ] T025 CRITICAL Close F1/T012's legacy migration with documented impacted consumers and tested native replacements, then retire the companion/custom outer-loop surfaces before a full platform release per Constitution II/Public Surface and FR-036; `docs/platform-compatibility.md` currently documents retention rather than compliance (contradicts).
- [ ] T026 Close F2/T013 with a bounded real vision-model browser fixture, legitimate session transfer/takeover and capability-mismatch evidence per FR-016/017/019 and SC-004; the corrected MCP lifetime and scripted-image transport gates do not establish live visual understanding (partial).
- [ ] T027 Close F3/T014 with the complete current AtBots Codex/Claude/Copilot role matrix, cancellation/unavailable cases and fault recovery per FR-038/039/040 and SC-010; retain the new real Copilot-proposal → Codex-worker validated artifact and report checks as measured cells, not universal runtime parity (partial).
- [ ] T028 Close F4/T017 by executing the current candidate's installed Python-floor and macOS/Windows/Linux matrix and recording exact versions/results per FR-037 and SC-009; keep Windows native AtSys workspace execution explicitly unsupported rather than infer it from a successful UI install (partial).
- [ ] T029 Close F5/T015 only when deployment is explicitly resumed and a project-specific spending grant exists: run real Cloud Run lifecycle/state/cleanup acceptance per FR-028/029/030/031/032 and SC-007; mocked/local tests remain separate. Cloud is deferred by the owner's current instruction (partial).
- [ ] T030 Close F6/T018 with measured live intent-routing outcomes across operation families, ambiguity, grants and untrusted input per FR-007/008 and SC-002; retain authored fixtures and the successful bounded Copilot tool checks separately, including its omitted-task-prefix failure and explicit read-only retry (partial).
