# Platform boundaries and governance migration

Dependent architecture constraints for constitution 4.0.0. This is not an
implementation report. No application code changed in the governance pass.

## Full product shape

```text
User: terminal / web conversation / explicit CLI / library
  |
Validated management operations + approvals + durable events
  |
Agent registry -- scoped workspace -- native conversations
  |                         |
  |                         +-- AtMem memory port (default)
  |
Execution owner
  +-- AtBot: native Pydantic AI + permitted tools/browser/MCP
  +-- AtSys: worker / observer / supervisor objective
                role-specific models and authoritative upstream state
  +-- AtFlows: optional model-call observability (not execution owner)

Durable schedules + runner leases + side-effect reconciliation
  |
Local runner / supported cloud runner
```

The management layer validates operations and coordinates lifecycle, not model
inference. Model selection and execution ownership are distinct: AtSys is not a
model vendor. Each agent and AtSys role can select a provider subject to feature
005's consent, entitlement and credential rules. No undeclared shared budget.

## Required implementation sequence

1. Registry/workspaces, typed operations and persistent native conversations;
   terminal create/reopen/configure/chat and tests. No cloud dependency.
2. AtMem adapter/controls; capture, applicable recall, provenance and corrections;
   scope, secret-filtering and degraded-memory tests.
3. Durable jobs/events/approvals, background execution, questions while busy,
   stop/result and budgets; inspectable real artifacts.
4. Browser MCP/vision, constrained file tools, approved skills and takeover;
   native payload tests and local fixture-site acceptance.
5. Durable scheduling with DST/overlap/restart tests, not only a cron wrapper.
6. Real optional AtFlows/AtSys adapters. Inspect installed supported contracts
   before choosing APIs. Demonstrate AtFlows model-call tracing and supervised
   fault recovery, not just mocked submission. Reuse AtSys 0.3.0b4 provider parity;
   do not duplicate its adapters or assume parity from executable detection.
7. Portable runtime and Cloud Run Jobs deploy/operate/cleanup. Transactional
   persistent state and explicit cloud secrets. Plans/mocks precede paid work.
8. First-party web client sharing service, policy and events with terminal;
   browser usability/security end-to-end tests.
9. Cross-platform/installed-package checks, docs, migration and convergence.
   Publication requires a separate explicit request.

Slices are ordering, not reduced scope. Browser, deployment, AtFlows and AtSys
remain required platform deliveries even if optional for one installed agent.
Persistent VM deployment can be a later additional target; SSH instructions
alone do not implement an adapter. No particular cheapest provider is guaranteed
without workload measurements and current pricing at deployment-plan time.

## Compatibility and conflict ledger

| Existing area | Decision | Required evidence |
| --- | --- | --- |
| 001 no named memory vendor in dependencies/core | Superseded; AtMem default behind a port | Real AtMem and substitute-backend tests |
| 001 developer-only/no-dashboard assumptions | Superseded; conversational terminal and optional web UI | Shared operation tests in both clients |
| 003 hand-written task-step loop | New platform uses native Pydantic AI loop | Grounding/failure/recovery eval migration |
| 004 deterministic and opt-in live evals | Preserve | Offline default gate; honest live reports |
| 005 authentication | Preserve/reuse | No token scraping, borrowed IDs or silent paid fallback |
| runtime.py AtMem capture/context/exposure | Reuse authority semantics behind adapter | No canonical write bypass or lost exposure controls |
| gateway.py/companion.py overlap | Audit, do not silently delete | Name each impacted consumer and replacement |
| Existing companion `serve` command | Not the new web control room | Explicit replacement/removal notice and compatibility tests |
| Existing configs | Preserve/import explicitly | Backup and versioned migration tests |
| Credentials/keychain | Remain local; export references only | Cloud secret provisioning, no implicit keychain copying |
| User edit to evals/baseline.json | Preserve | No re-generation or broad automatic commit |

## Security and operational constraints

### AtSys multi-runtime boundary

Latest inspection on 2026-10-26: AtSys local and remote main both point to
`c19ab97e80714981b5b146e7efc238a7cdfa32b6`, merging provider parity. Feature
`specs/008-provider-parity` and release 0.3.0b4 supply real codex/claude/copilot
workers, independent supervisor/repair providers, native CLI invocation, strict
results and portable hooks. This supersedes the earlier Codex-only finding.

AtBots must consume that runtime-adapter boundary. Existing deterministic policy,
leases, budgets, validator receipts and proposal parsers remain AtSys-owned.
Do not copy supervisor/repair logic or bypass its daemon. Map worker/model,
supervisorProvider/supervisorModel and repairProvider/repairModel explicitly.

Runtime choice (`codex`, `claude`, `copilot`) is separate from model choice.
Worker/supervisor and optional model-based observer bindings must be explicit.
Configured cross-runtime recovery is allowed only inside enforceable permission
boundaries. CLI permission controls are not automatically equivalent to an OS
sandbox. If a required read-only or network boundary cannot be enforced, report
unsupported before starting that role; do not rely on prompt instructions alone.

Feature-005 provider OAuth is distinct from native coding-CLI authentication.
Use each CLI's supported existing login; no credential copying, token scraping,
API billing assumptions or automatic reauthentication. Record each runtime's
tested version, effective capabilities and observed telemetry. Unknown cost stays
unknown; native resume, usage and hooks are not implied by basic execution.

Do not create the previously proposed duplicate AtSys feature directory. Existing
`specs/008-provider-parity/verification.md` records 99 backend tests, 20 browser
checks and short live worker acceptance for all three providers. Live supervisor/
repair fault recovery remains fixture-tested rather than live-qualified by those
worker runs; native provider-session resume is not claimed. Claude/Copilot shell
execution requires explicit trustedLocalExecution and is not a Codex OS sandbox.
AtBots still needs its own integration acceptance against this dependency.

Enforce policy in operations/tools, not merely prompts. A workspace directory
does not sandbox Python/shell execution. Arbitrary-code agents need real sandbox
boundaries and limited identities. Filesystem traversal and symlinks need tests.

Cookies are credentials. Portable manifests exclude them; authorized session
transfer uses a separate encrypted path and may require destination login.
Screenshots may contain private information and need retention/redaction policy.
Models without vision get an appropriate toolset or explicit capability error.

Cost controls include role models, browser time, compute, storage and transfer.
Billing alerts alone are not hard caps. Unknown prices mean the dollar cap is
unverified; known token/time/request admission limits still apply. Subscription
sign-in does not prove unattended cloud execution entitlement.

Pause prevents new work and requests safe suspension; cancellation reaches the
execution owner. Neither undoes an already-sent message. Restart must reconcile
uncertain actions before replay. No competing local/cloud runner writers.

## Implementation handoff

The earlier governance-only pass is complete. Implementation now follows plan.md
and tasks.md against this full scope. No package publication, paid cloud deployment
or installed AtSys service replacement is implied. Preserve existing authentication
work and the user-owned evaluation baseline.
