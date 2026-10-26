# 005 — Provider authentication

> Scope update, 2026-10-26: feature 006 consumes this contract for per-agent and
> control-room model selection. It does not broaden consent, entitlement or
> credential-export rights. Constitution 4.0.0 permits default AtMem and a
> first-party control room; it does not certify legacy companion or outer-loop code.

User-confirmed directory, 2026-10-26. Add explicit account sign-in for ChatGPT and GitHub Copilot while preserving Ollama and API-key behavior. Anthropic's published third-party authentication restriction means Claude.ai subscription OAuth is explicitly unsupported here; offer its native API-key provider instead. No account policy bypass, borrowed client ID, token scraping or subscription billing promise.

## Requirements

- FR-001: `atbots auth login|status|logout` supports `chatgpt` and `github-copilot`, named local profiles and bounded interactive browser/device authorization. Login never silently enables inference or remote egress. GitHub uses an explicitly configured app client ID, not another application's identity.
- FR-002: Reuse native Pydantic AI OAuth, provider and model implementations; retain its Agent, structured outputs, capability/tool hooks and usage. No nested coding CLI/agent loop or new model wire protocol.
- FR-003: Persist secrets only through an available approved OS credential backend; fail closed without it. Never write tokens into config, source, plaintext files or diagnostics. Serialize login/inference refresh/logout across processes for a profile; refresh saves must persist before the next process uses the credentials.
- FR-004: Status distinguishes missing login, expired/relogin needed, identity-only versus plan-usage consent, and unverified model entitlement. Status never triggers login, model calls or automatic refresh. Local logout deletes AtBots' credential only; remote revocation is a separate provider operation.
- FR-005: Explicit `chatgpt` and `github-copilot` provider kinds use stored credentials with Pydantic AI models. Expiring Copilot grants require sign-in again; do not claim automatic renewal that upstream does not provide. ChatGPT automatic refresh remains upstream-owned. Missing authorization never silently becomes another paid provider. Existing remote/sensitive-content policy remains active.
- FR-006: `anthropic` kind uses the native Pydantic AI Anthropic model/API-key provider. `auth login anthropic` explicitly explains why subscription OAuth is unsupported; never opens a spoofed flow. Authentication failures contain no provider response/token dumps.
- FR-007: Optional auth/Anthropic extras fail with actionable instructions when absent. Old configs and Ollama default remain readable and unchanged. Model IDs are explicit user choices; no model entitlement inferred from login or catalog.
- FR-008: Offline tests cover consent/denial, cancellation/timeout, expiry, rotation save, logout, secure-store failure, remote gating, routing, native structured output and backward compatibility. Live sign-in/inference is not required or simulated as real acceptance. Document exact commands and provider limits.

## Scenarios / success

Login using a browser (ChatGPT) or own-app device code (Copilot), save only in OS keychain, inspect redacted state, explicitly configure the provider and remote egress, then run a normal TaskAgent task. Logout removes that profile and blocks its future use. An identity-only ChatGPT grant cannot power inference. Expired Copilot credentials require reauthorization. Unsupported Anthropic OAuth fails without token access; API-key inference remains available. Existing local tests and new auth tests pass in a dependency-conforming isolated environment. No release or credential-changing live login is part of implementation verification.
