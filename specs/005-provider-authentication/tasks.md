# Tasks

## Phase 1 — Contracts and secure storage
- [x] [T001] Define lazy native auth dependency extras and secure keyring/profile-lock implementation in `pyproject.toml`, `src/atbots/auth.py` (FR-001, FR-002, FR-003, FR-004, FR-007).
- [x] [T002] Implement ChatGPT/Copilot sign-in, consent/expiry checks, redacted status/logout and Anthropic OAuth refusal in `src/atbots/auth.py` (FR-001, FR-003, FR-004, FR-006).

## Phase 2 — Runtime and user configuration
- [x] [T003] Add native authenticated model provider and router/config integration in `src/atbots/providers/authenticated.py`, `router.py`, `config.py` (FR-002, FR-005, FR-006, FR-007).
- [x] [T004] Expose `auth login/status/logout` independently of companion startup in `src/atbots/cli.py` (FR-001, FR-004, FR-006, FR-007).

## Phase 3 — Verification and handoff
- [x] [T005] Add offline auth, store/rotation, native HTTP, routing and CLI tests in `tests/test_auth.py`; run existing non-live suite, dependency checks and artifact gates (FR-008 plus FR-001–007).
- [x] [T006] Document provider support/commands, consent, own GitHub app ID, secure storage, expiry and no live entitlement guarantee in `README.md` and `specs/005-provider-authentication/verification.md` (FR-004, FR-005, FR-006, FR-007, FR-008).
