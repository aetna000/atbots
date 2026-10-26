# Tasks — full platform

## Phase 1: Persistent agent foundation

- [x] [T001] Implement strict agent/provider/limit contracts and private SQLite registry, stable-ID workspaces, validation, revisions and isolated history in `src/atbots/platform/models.py`, `store.py`; add `tests/test_platform_store.py` (FR-002/003/006/009). Evidence: 23 deterministic tests passed on macOS/Python 3.12.
- [x] [T002] Implement native Pydantic AI sessions with exposed Agent, configured model selection, native history, bounded usage/time, per-conversation serialization and safe failure reporting in `platform/session.py`; reuse auth model construction and test real native Agent with TestModel/FunctionModel (FR-005/006/009/012/017). Evidence: native tool/history/limit tests and real local Ollama reply; vision acceptance belongs to T006.
- [x] [T003] Implement terminal create/list/inspect/configure/chat and interactive control room with schema-validated conversational intents and explicit remote grants in `platform/cli.py`, `control.py`, root `cli.py`; test dispatch, clarification, model selection and no silent fallback (FR-001/004/007/008/011). Evidence: deterministic dispatch/approval tests plus real local-model create/list smoke. Durable approvals and fleet background state remain T005.

## Phase 2: Memory and durable execution

- [x] [T004] Implement AtMem memory port, applicable recall/exposure, eligible capture, inspect/correct/forget/share and secret-filtering boundaries in `platform/memory.py`; real AtMem and substitute-backend tests (FR-013/014/015, SC-003). Implemented native authority operations, rules-based user capture, approved control-room mutations and directional revocable sharing; real-backend tests pass. Automatic formation is limited to AtMem's deterministic extraction coverage, not a claim of multilingual semantic completeness.

  Evidence: ten real memory/control tests plus substitute-port, privacy and native
  session regression coverage. Sharing is read-only, non-transitive and bounded
  to three shared sources per recall; revocation cannot undo prior exposure.
- [ ] [T005] Implement durable jobs/events, background execution, questions while busy, approval lifecycle, cancellation, leases and side-effect reconciliation in `platform/jobs.py`; fault and concurrency tests (FR-010/011/012/020/021/023/035).
- [ ] [T006] Implement upstream browser MCP/vision, approved-root file tools, browser takeover, domain/action permissions and reviewed skill management in `platform/browser.py`, `skills.py`; real local browser fixture acceptance (FR-016/017/018/019, SC-004).
- [ ] [T007] Implement persisted scheduling, timezone/DST, overlap, missed-run policies, previews and runner lifecycle in `platform/scheduler.py`; deterministic clock/restart tests (FR-022/023, SC-005).

## Phase 3: Integrations and deployment

- [ ] [T008] Implement optional AtSys 0.3.0b4 adapter with role providers/models and trusted-local grants, plus AtFlows compatible tracing/telemetry in `platform/integrations/`; verify live task/report and tracing paths, fault recovery and explicit unsupported capabilities (FR-024/025/026/027/038/039/040, SC-006/010).
- [ ] [T009] Implement portable export/import/move and Cloud Run Jobs deploy/plan/status/logs/stop/destroy, pinned container, external state and cloud secrets in `platform/deployment/`; isolated cloud acceptance under an explicit spending grant (FR-028/029/030/031/032, SC-007).
- [ ] [T010] Implement authenticated first-party web control room on shared operations/events; browser checks for conversation, permissions, artifacts and deployment at desktop/mobile sizes (FR-033, SC-008).

## Phase 4: Full acceptance and packaging

- [ ] [T011] Finish doctor/preflight, legacy migration/removal notices, intent evals, pip extras/guides, installed-wheel and macOS/Windows/Linux acceptance; record blockers and run convergence in `docs/`, `tests/`, `specs/006-agent-control-room/verification.md` (FR-034/036/037, SC-001/002/009).
