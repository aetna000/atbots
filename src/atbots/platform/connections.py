"""Reusable provider connections; secret values never enter agent configuration."""

import asyncio
import json
import re
import threading
import uuid
from typing import Literal
from urllib.request import ProxyHandler, build_opener

from pydantic import Field

from atbots.auth import AuthError, CredentialStore, auth_status, login, profile_lock
from atbots.platform.memory import screen_message
from atbots.platform.models import Contract, ModelBinding
from atbots.platform.store import StoreError

KEY_SERVICE = "atbots.api-keys.v1"


class APIKeys:
    def __init__(self):
        self.backend = CredentialStore().backend

    @staticmethod
    def validate(profile):
        if not re.fullmatch(r"key-[a-f0-9]{32}", profile):
            raise AuthError("Invalid saved API credential reference")

    def load(self, profile):
        self.validate(profile)
        try:
            value = self.backend.get_password(KEY_SERVICE, profile)
        except Exception:  # noqa: BLE001 - keychain errors can contain credential values
            raise AuthError("Unlock the OS keychain to use this connection") from None
        if not value:
            raise AuthError("Saved API credential is missing; reconnect in Setup")
        return value

    def save(self, profile, value):
        self.validate(profile)
        if (
            not isinstance(value, str)
            or not 10 <= len(value) <= 8192
            or any(c.isspace() for c in value)
        ):
            raise AuthError("Enter a valid API credential without whitespace")
        try:
            self.backend.set_password(KEY_SERVICE, profile, value)
        except Exception:  # noqa: BLE001 - keychain errors can contain credential values
            raise AuthError(
                "Cannot save the API credential in the OS keychain"
            ) from None


class Connection(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")
    label: str = Field(min_length=1, max_length=80)
    kind: Literal[
        "ollama", "openai-compatible", "anthropic", "chatgpt", "github-copilot"
    ]
    endpoint: str
    auth_profile: str = "default"


def api_key(binding):
    """Resolve a configured reference only, never discover another app's secrets."""
    import os

    if binding.api_key_env:
        value = os.environ.get(binding.api_key_env)
        if not value:
            raise AuthError("Configured API-key environment variable is missing")
        return value
    if binding.auth_profile.startswith("key-"):
        return APIKeys().load(binding.auth_profile)
    raise AuthError("Connect this provider in Setup first")


class Connections:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS provider_connections(id TEXT PRIMARY KEY,definition TEXT NOT NULL)"
            )

    def list(self):
        with self.store.connect() as db:
            rows = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT definition FROM provider_connections ORDER BY id"
                )
            ]
        defaults = [
            Connection(
                id="local",
                label="Local Ollama",
                kind="ollama",
                endpoint="http://127.0.0.1:11434",
            ).model_dump()
        ]
        # Reuse only AtBots' own saved native profiles. No inference or login.
        for kind, label in (
            ("github-copilot", "GitHub Copilot"),
            ("chatgpt", "ChatGPT / Codex account"),
        ):
            status = auth_status(kind)
            if status["state"] == "saved":
                defaults.append(
                    Connection(
                        id="saved-" + kind,
                        label=label,
                        kind=kind,
                        endpoint="https://api.githubcopilot.com"
                        if kind == "github-copilot"
                        else "https://api.openai.com/v1",
                    ).model_dump()
                )
        return defaults + rows

    def get(self, identity):
        for value in self.list():
            if value["id"] == identity:
                return Connection.model_validate(value)
        raise StoreError("Connection is unavailable; open Setup to connect it")

    def save_api(self, kind, label, key):
        if kind not in {"openai-compatible", "anthropic"}:
            raise ValueError("Choose OpenAI API or Anthropic API")
        screen_message(label)
        identity = uuid.uuid4().hex
        connection = Connection(
            id="api-" + identity,
            label=label,
            kind=kind,
            endpoint="https://api.anthropic.com"
            if kind == "anthropic"
            else "https://api.openai.com/v1",
            auth_profile="key-" + identity,
        )
        APIKeys().save(connection.auth_profile, key)
        self._save(connection)
        return connection.model_dump()

    def _save(self, connection):
        screen_message(connection.model_dump_json())
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO provider_connections VALUES (?,?)",
                (connection.id, connection.model_dump_json()),
            )

    def binding(self, identity, model):
        connection = self.get(identity)
        return ModelBinding(
            kind=connection.kind,
            model=model,
            endpoint=connection.endpoint,
            auth_profile=connection.auth_profile,
            egress_class="local" if connection.kind == "ollama" else "remote",
        )

    def models(self, identity):
        connection = self.get(identity)
        try:
            values = asyncio.run(self._models(connection))
        except Exception:  # noqa: BLE001 - provider errors must not expose credentials
            raise StoreError(
                "Model discovery failed. Check the connection, sign-in permission and provider access in Setup; no inference was attempted"
            ) from None
        return {
            "connection": identity,
            "models": sorted(set(values))[:500],
            "inference_access": "not_tested",
            "source": "provider_catalog",
        }

    async def _models(self, connection):
        if connection.kind == "ollama":
            # Fixed loopback endpoint, bounded response, no ambient proxy.
            with build_opener(ProxyHandler({})).open(
                connection.endpoint + "/api/tags", timeout=10
            ) as r:
                raw = r.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Model catalog is too large")
            return [
                m["name"]
                for m in json.loads(raw).get("models", [])
                if not m.get("capabilities") or "completion" in m["capabilities"]
            ]
        if connection.kind == "anthropic":
            from anthropic import AsyncAnthropic

            async with AsyncAnthropic(
                api_key=APIKeys().load(connection.auth_profile),
                timeout=20,
                max_retries=0,
            ) as client:
                page = await client.models.list(limit=100)
                return [m.id for m in page.data]
        if connection.kind == "openai-compatible":
            from openai import AsyncOpenAI

            async with AsyncOpenAI(
                api_key=APIKeys().load(connection.auth_profile),
                base_url=connection.endpoint,
                timeout=20,
                max_retries=0,
            ) as client:
                page = await client.models.list()
                return [m.id for m in page.data]
        from atbots.config import ProviderConfig
        from atbots.providers.authenticated import AuthenticatedProvider

        with profile_lock(connection.kind, connection.auth_profile, timeout=0):
            provider = AuthenticatedProvider(
                ProviderConfig(
                    name="setup",
                    kind=connection.kind,
                    model="catalog-only",
                    egress_class="remote",
                    auth_profile=connection.auth_profile,
                ),
                capability_refs=[],
                retries=0,
            )
            async with provider.model_context() as model:
                page = await model.client.models.list(timeout=20)
                values = []
                for item in page.data:
                    endpoints = item.model_dump().get("supported_endpoints")
                    if (
                        connection.kind != "github-copilot"
                        or not endpoints
                        or "/chat/completions" in endpoints
                    ):
                        values.append(item.id)
                return values


class SignIns:
    """Bounded native sign-in jobs. Only public progress/device codes reach UI."""

    def __init__(self, connections):
        self.connections = connections
        self.jobs = {}
        self.lock = threading.Lock()

    def start(self, provider, client_id=None):
        if provider not in {"chatgpt", "github-copilot"}:
            raise ValueError(
                "Use API-key setup for Anthropic; subscription OAuth is unsupported"
            )
        with self.lock:
            if any(j["state"] == "waiting" for j in self.jobs.values()):
                raise StoreError("Finish the current browser sign-in first")
            if len(self.jobs) >= 50:
                self.jobs = {
                    k: v for k, v in self.jobs.items() if v["state"] == "waiting"
                }
            identity = uuid.uuid4().hex
            self.jobs[identity] = {
                "id": identity,
                "provider": provider,
                "state": "waiting",
                "message": "Complete sign-in in your browser",
            }

        def notify(message):
            with self.lock:
                self.jobs[identity]["message"] = message

        def run():
            try:
                status = asyncio.run(
                    login(
                        provider,
                        profile="default",
                        client_id=client_id,
                        notify=notify,
                        timeout=300,
                    )
                )
                with self.lock:
                    self.jobs[identity].update(
                        state="connected"
                        if status["state"] == "saved"
                        else "permission_required",
                        message="Connected; discover your models next"
                        if status["state"] == "saved"
                        else "Sign-in succeeded but plan-usage permission is not enabled",
                    )
            except Exception:  # noqa: BLE001 - sanitize native sign-in errors
                with self.lock:
                    self.jobs[identity].update(
                        state="failed",
                        message="Sign-in failed or timed out. Check your device-enabled Client ID, keychain and provider consent, then try again",
                    )

        threading.Thread(target=run, daemon=True).start()
        return self.get(identity)

    def get(self, identity):
        with self.lock:
            if identity not in self.jobs:
                raise StoreError("Unknown sign-in; start again in Setup")
            return dict(self.jobs[identity])
