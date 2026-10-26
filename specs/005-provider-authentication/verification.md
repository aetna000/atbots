# Provider authentication verification

Date: 2026-10-26. Branch: `005-provider-authentication`. Source feature only; package version remains `0.2.0`. No release, commit or push was performed.

## Results

- macOS, Python 3.12, isolated pip environment: `/tmp/atbots-auth-oEWbti/venv`.
- Source non-live suite: 107 passed; 6 live tests deselected.
- Built wheel installed into that environment; authentication suite run outside the repository against installed modules: 41 passed. These are a subset of the 107 tests, not additional distinct cases.
- Installed import verified under `site-packages`, CLI `auth --help` works, and wheel metadata exposes `auth` and `anthropic` extras.
- Wheel and source distribution build succeeded; `pip check` reports no broken requirements.
- New authentication modules/tests pass Ruff checks and formatting. Changed Python modules parse with Python 3.10 grammar; this is not a Python 3.10 runtime test.
- Verified dependency versions include Pydantic AI slim 2.61.0, keyring 25.7.0 and filelock 3.32.7. Global Python packages were not upgraded.

Reproduce source tests:

```sh
python -m pip install -e ".[auth,anthropic,dev]"
python -m pytest -m 'not eval' -q
```

## Coverage and boundaries

Offline tests exercise consent and denial, cancellation and timeout, identity-only grants, Copilot expiry, secure-store failures, profile isolation, process locking, rotation persistence and local logout. Native Pydantic models and Agent structured outputs are exercised with mocked HTTP for ChatGPT Responses streaming, Copilot chat completions and Anthropic messages. Native ChatGPT 401 refresh tests verify both successful rotated-token persistence and failure-before-replay when persistence fails. Tokens in tests are fake.

Remote egress and sensitive-content policy remain enforced. An unavailable explicitly selected account provider does not silently select a different paid provider. Existing Ollama/configuration tests pass. Credentials are stored only in approved OS keychains; plaintext and chained fallbacks are refused. Authentication status is local and explicitly does not certify inference entitlement. Logout removes the local AtBots grant, not remote app authorization.

No actual account sign-in, paid inference, production keychain operation, Windows/Linux host acceptance, or provider entitlement has been verified. GitHub requires the user's own device-enabled OAuth app ID. Expired Copilot grants require re-login. Anthropic subscription OAuth is explicitly unsupported; its native API-key path is implemented instead. ChatGPT requires plan-usage consent in addition to identity sign-in.

Preexisting constitution drift involving the legacy companion surface, memory vendor dependency and outer task orchestration remains outside this bounded authentication change. This verification does not certify whole-repository constitutional compliance. The preexisting user modification to `evals/baseline.json` was preserved.
