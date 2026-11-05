"""Native provider sign-in; secrets stay in the OS credential store.

No CLI credential scraping, HTTP compatibility bridge or borrowed OAuth client.
Imports are lazy so the local agent works without the auth extra.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import math
import re
import secrets
import time
import webbrowser
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any

from atbots.config import DEFAULT_ROOT

PROVIDERS = ("chatgpt", "github-copilot")
SERVICE = "atbots.provider-auth.v1"
CHUNK_SIZE = 1000  # ASCII characters; at most 2000 bytes with Windows UTF-16 storage
MAX_CHUNKS = 128
ANTHROPIC_NOTICE = (
    "Claude.ai subscription OAuth is not supported in this third-party app. "
    "Use kind='anthropic' with an explicitly configured Anthropic API key, "
    "or sign in to Anthropic's own unmodified Claude Code separately."
)


class AuthError(RuntimeError):
    """Safe user-facing failure; never include underlying credential payloads."""


def validate_profile(provider: str, profile: str) -> None:
    if provider == "anthropic":
        raise AuthError(ANTHROPIC_NOTICE)
    if provider not in PROVIDERS:
        raise AuthError("Unsupported authentication provider")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", profile):
        raise AuthError(
            "Profile must be 1–64 letters, numbers, dots, underscores or hyphens"
        )


def native_module(provider: str) -> Any:
    name = "openai_chatgpt" if provider == "chatgpt" else "github_copilot"
    try:
        return importlib.import_module(f"pydantic_ai.providers.{name}")
    except ImportError:
        raise AuthError(
            'Install authentication support: python -m pip install "atbots[auth]"'
        ) from None


class CredentialStore:
    """Only approved native OS backends; never fall back to a plaintext file."""

    def __init__(self) -> None:
        try:
            import keyring

            backend = keyring.get_keyring()
            module = type(backend).__module__
            approved = (
                "keyring.backends.macOS",
                "keyring.backends.Windows",
                "keyring.backends.SecretService",
                "keyring.backends.libsecret",
                "keyring.backends.kwallet",
            )
            if module not in approved or backend.priority <= 0:
                raise AuthError(
                    "A supported OS keychain is required; plaintext/chained backends are refused"
                )
            self.backend = backend
        except AuthError:
            raise
        except Exception:  # noqa: BLE001 - backend exceptions may contain secrets
            raise AuthError(
                'OS credential store unavailable; install "atbots[auth]" and unlock your keychain'
            ) from None

    def _chunk_services(self, account: str, manifest: Any) -> list[str]:
        if not isinstance(manifest, dict) or manifest.get("format") != "chunks-v1":
            return []
        generation, count = manifest.get("generation"), manifest.get("count")
        if (not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{32}", generation)
                or type(count) is not int or not 1 <= count <= MAX_CHUNKS):
            raise ValueError("Invalid credential manifest")
        account_hash = hashlib.sha256(account.encode()).hexdigest()
        return [f"{SERVICE}.chunk.{account_hash}.{generation}.{i}" for i in range(count)]

    def _cleanup_chunks(self, account: str, services: list[str]) -> None:
        for service in services:
            try:
                self.backend.delete_password(service, account)
            except Exception:  # best effort after the committed value has changed
                pass

    def load(self, provider: str, profile: str) -> dict[str, Any] | None:
        validate_profile(provider, profile)
        try:
            account = f"{provider}:{profile}"
            raw = self.backend.get_password(SERVICE, account)
            if raw is None:
                return None
            value = json.loads(raw)
            services = self._chunk_services(account, value)
            if services:
                chunks = [self.backend.get_password(service, account) for service in services]
                if any(not isinstance(chunk, str) for chunk in chunks):
                    raise ValueError("Missing credential chunk")
                value = json.loads("".join(chunks))
            if (
                not isinstance(value, dict)
                or value.get("version") != 1
                or not isinstance(value.get("credentials"), dict)
            ):
                raise ValueError()
            return value
        except Exception:  # noqa: BLE001 - redact credential backend/JSON failures
            raise AuthError(
                "Cannot read saved authentication; unlock the keychain or sign in again"
            ) from None

    def save(self, provider: str, profile: str, credentials: Any) -> None:
        validate_profile(provider, profile)
        written = []
        committed = False
        account = f"{provider}:{profile}"
        try:
            value = {
                "version": 1,
                "issued_at": time.time(),
                "credentials": asdict(credentials),
            }
            raw = json.dumps(value, ensure_ascii=True)
            if type(self.backend).__module__ == "keyring.backends.Windows":
                old_raw = self.backend.get_password(SERVICE, account)
                old_services = self._chunk_services(account, json.loads(old_raw)) if old_raw else []
                count = max(1, (len(raw) + CHUNK_SIZE - 1) // CHUNK_SIZE)
                if count > MAX_CHUNKS:
                    raise ValueError("Credential exceeds storage limit")
                manifest = {"format": "chunks-v1", "generation": secrets.token_hex(16), "count": count}
                services = self._chunk_services(account, manifest)
                for i, service in enumerate(services):
                    written.append(service)
                    self.backend.set_password(service, account, raw[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE])
                self.backend.set_password(SERVICE, account, json.dumps(manifest))
                committed = True
                self._cleanup_chunks(account, old_services)
            else:
                self.backend.set_password(SERVICE, account, raw)
        except Exception:  # noqa: BLE001 - persistence failures must not echo tokens
            if not committed:
                self._cleanup_chunks(account, written)
            raise AuthError(
                "Cannot persist authentication; no plaintext fallback was written. Sign in again before retrying"
            ) from None

    def delete(self, provider: str, profile: str) -> bool:
        if self.load(provider, profile) is None:
            return False
        try:
            account = f"{provider}:{profile}"
            raw = self.backend.get_password(SERVICE, account)
            services = self._chunk_services(account, json.loads(raw))
            self.backend.delete_password(SERVICE, account)
            self._cleanup_chunks(account, services)
            return True
        except Exception:  # noqa: BLE001 - redact native backend errors
            raise AuthError(
                "Cannot remove saved authentication; unlock the keychain and retry"
            ) from None


@contextmanager
def profile_lock(provider: str, profile: str, timeout: float = 30) -> Iterator[None]:
    validate_profile(provider, profile)
    try:
        from filelock import FileLock, Timeout
    except ImportError:
        raise AuthError(
            'Install authentication support: python -m pip install "atbots[auth]"'
        ) from None
    root = DEFAULT_ROOT / "auth-locks"
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = hashlib.sha256(f"{provider}:{profile}".encode()).hexdigest()
        lock = FileLock(str(root / f"{name}.lock"), timeout=timeout, mode=0o600)
        with lock:
            yield
    except Timeout:
        raise AuthError(
            "This profile is busy; wait for its other login/request/logout to finish"
        ) from None


def credential_state(provider: str, value: dict[str, Any] | None) -> str:
    if value is None:
        return "signed_out"
    raw = value["credentials"]
    if not isinstance(raw.get("access_token"), str) or not raw["access_token"]:
        return "relogin_required"
    if provider == "chatgpt":
        if not raw.get("client_id") or not raw.get("refresh_token"):
            return "relogin_required"
        scope = raw.get("scope", "")
        if not isinstance(scope, str):
            return "relogin_required"
        return (
            "saved" if "chatgpt.tokens.use.direct" in scope.split() else "identity_only"
        )
    expires = raw.get("expires_in")
    issued = value.get("issued_at")
    if expires is not None and (
        isinstance(expires, bool)
        or not isinstance(expires, (float, int))
        or not isinstance(issued, (float, int))
        or isinstance(issued, bool)
        or not math.isfinite(expires)
        or not math.isfinite(issued)
        or expires <= 0
        or issued + expires <= time.time() + 30
    ):
        return "relogin_required"
    return "saved"


def auth_status(
    provider: str, profile: str = "default", *, store: Any = None
) -> dict[str, Any]:
    validate_profile(provider, profile)
    try:
        value = (store or CredentialStore()).load(provider, profile)
        state = credential_state(provider, value)
        return {
            "provider": provider,
            "profile": profile,
            "state": state,
            "inference_access": "unverified",
            "live_checked": False,
            "renewal": "provider_on_use"
            if provider == "chatgpt"
            else "sign_in_again_on_expiry",
        }
    except AuthError:
        return {
            "provider": provider,
            "profile": profile,
            "state": "store_unavailable",
            "inference_access": "unverified",
            "live_checked": False,
        }


async def login(
    provider: str,
    profile: str = "default",
    *,
    client_id: str | None = None,
    timeout: float = 300,
    store: Any = None,
    notify: Callable[[str], Any] = print,
    open_browser: Callable[[str], Any] = webbrowser.open,
) -> dict[str, Any]:
    validate_profile(provider, profile)
    if isinstance(timeout, bool) or not 1 <= timeout <= 900:
        raise AuthError("Login timeout must be between 1 and 900 seconds")
    native = native_module(provider)
    target = store or CredentialStore()  # fail before opening authorization

    async def authorize() -> dict[str, Any]:
        if provider == "chatgpt":
            saved = target.load(provider, profile)
            raw = saved["credentials"] if saved else {}
            flow = native.OpenAIChatGPTOAuthFlow(
                app_name="AtBots",
                client_id=raw.get("client_id"),
                id_token_hint=raw.get("id_token"),
            )
            # Never print an authorization URL: re-login may include an ID token.
            notify(
                "Opening ChatGPT sign-in in your browser. Approve AtBots and plan usage if desired."
            )
            url = flow.authorization_url(extra_params={"prompt": "consent"})
            if not open_browser(url):
                raise AuthError(
                    "Browser could not open; run login on a desktop with a working browser"
                )
            credentials = await flow.exchange_code_from_callback()
        else:
            if not client_id or not client_id.strip():
                raise AuthError(
                    "GitHub Copilot requires --client-id for your own device-enabled GitHub OAuth app"
                )
            flow = native.GitHubCopilotOAuthFlow(client_id=client_id)
            authorization = await flow.start()
            notify(
                f"Open {authorization.verification_uri} and enter {authorization.user_code}. "
                "Approve only the code from this login attempt."
            )
            credentials = await flow.wait_for_authorization()
        target.save(provider, profile, credentials)
        return auth_status(provider, profile, store=target)

    try:
        with profile_lock(provider, profile, timeout=1):
            return await asyncio.wait_for(authorize(), timeout=timeout)
    except (AuthError, asyncio.CancelledError):
        raise
    except asyncio.TimeoutError:
        raise AuthError("Login timed out; no new credentials were saved") from None
    except Exception:  # noqa: BLE001 - OAuth errors may include token responses
        raise AuthError(
            "Provider sign-in failed or was denied; no new credentials were saved"
        ) from None


def logout(
    provider: str, profile: str = "default", *, store: Any = None
) -> dict[str, Any]:
    validate_profile(provider, profile)
    with profile_lock(provider, profile):
        removed = (store or CredentialStore()).delete(provider, profile)
    return {
        "provider": provider,
        "profile": profile,
        "removed": removed,
        "remote_revoked": False,
        "note": "Local AtBots credential removed; revoke app access in provider settings separately",
    }


def chatgpt_source(profile: str, store: Any) -> Any:
    native = native_module("chatgpt")

    class Source(native.OpenAIChatGPTCredentialSource):
        async def load(self) -> Any:
            value = store.load("chatgpt", profile)
            if credential_state("chatgpt", value) != "saved":
                raise AuthError(
                    "ChatGPT plan usage is not authorized; sign in and grant plan usage"
                )
            return native.OpenAIChatGPTCredentials(**value["credentials"])

        async def save(self, credentials: Any) -> None:
            store.save("chatgpt", profile, credentials)

    return Source()
