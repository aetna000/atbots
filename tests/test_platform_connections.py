import json
import sys
import time
import uuid

import pytest

from atbots.auth import AuthError
from atbots.platform import connections as module
from atbots.platform.connections import APIKeys, Connections, SignIns
from atbots.platform.store import AgentStore, StoreError


@pytest.fixture
def vault(monkeypatch):
    values = {}

    class Backend:
        def get_password(self, service, profile):
            return values.get((service, profile))

        def set_password(self, service, profile, value):
            values[service, profile] = value

    monkeypatch.setattr(
        module, "CredentialStore", lambda: type("Vault", (), {"backend": Backend()})()
    )
    monkeypatch.setattr(
        module,
        "auth_status",
        lambda kind: {"state": "saved" if kind == "github-copilot" else "missing"},
    )
    return values


def test_connect_once_reuse_binding_without_serializing_key(tmp_path, vault):
    store = AgentStore(tmp_path)
    connections = Connections(store)
    row = connections.save_api(
        "openai-compatible", "OpenAI API", "fixture-not-a-real-credential"
    )
    assert len(vault) == 1
    binding = connections.binding(row["id"], "fixture-model")
    assert module.api_key(binding) == "fixture-not-a-real-credential"
    store.create("coder", binding=binding, remote_allowed=True)
    store.create("writer", binding=binding, remote_allowed=True)
    assert "fixture-not-a-real-credential" not in store.database.read_bytes().decode(
        errors="ignore"
    )
    assert store.get("coder").id != store.get("writer").id
    assert connections.get("saved-github-copilot").auth_profile == "default"


def test_catalog_uses_provider_results_no_inference_claim(tmp_path, monkeypatch, vault):
    connections = Connections(AgentStore(tmp_path))

    async def catalog(self, connection):
        assert connection.id == "local"
        return ["model-b", "model-a", "model-b"]

    monkeypatch.setattr(Connections, "_models", catalog)
    result = connections.models("local")
    assert result["models"] == ["model-a", "model-b"]
    assert result["inference_access"] == "not_tested"


def test_secret_errors_are_redacted_and_invalid_refs_fail(tmp_path, monkeypatch, vault):
    connections = Connections(AgentStore(tmp_path))

    async def fail(*args):
        raise RuntimeError("secret-provider-response")

    monkeypatch.setattr(Connections, "_models", fail)
    with pytest.raises(StoreError) as error:
        connections.models("local")
    assert "secret-provider-response" not in str(error.value)
    with pytest.raises(AuthError):
        APIKeys().load("../wrong")
    with pytest.raises(ValueError, match="unsupported"):
        SignIns(connections).start("anthropic")
    assert "secret" not in json.dumps(connections.list())


def test_windows_large_api_key_roundtrip_and_failed_replacement(monkeypatch):
    values = {}
    class Backend:
        __module__ = "keyring.backends.Windows"
        fail = False

        def get_password(self, service, profile):
            return values.get((service, profile))

        def set_password(self, service, profile, value):
            assert len(value.encode("utf-16-le")) <= 2560
            if self.fail and service == module.KEY_SERVICE:
                raise RuntimeError("secret")
            values[service, profile] = value

        def delete_password(self, service, profile):
            del values[service, profile]

    backend = Backend()
    class Vault(module.CredentialStore):
        def __init__(self):
            self.backend = backend

    monkeypatch.setattr(module, "CredentialStore", Vault)
    keys = APIKeys()
    profile = "key-" + "a" * 32
    original = "x" * 8000
    keys.save(profile, original)
    assert keys.load(profile) == original
    old = values.copy()
    backend.fail = True
    with pytest.raises(AuthError):
        keys.save(profile, "replacement-key")
    assert values == old
    backend.fail = False
    keys.save(profile, "replacement-key")
    assert keys.load(profile) == "replacement-key"
    assert len(values) == 2


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows Credential Manager")
def test_windows_real_credential_manager_large_synthetic_api_key():
    keys = APIKeys()
    assert type(keys.backend).__module__ == "keyring.backends.Windows"
    profile = "key-" + uuid.uuid4().hex
    value = "synthetic-" + "x" * 7900
    try:
        keys.save(profile, value)
        assert keys.load(profile) == value
    finally:
        raw = keys.backend.get_password(module.KEY_SERVICE, profile)
        if raw:
            manifest = json.loads(raw)
            services = module.CredentialStore._chunk_services(keys, profile, manifest)
            keys.backend.delete_password(module.KEY_SERVICE, profile)
            module.CredentialStore._cleanup_chunks(keys, profile, services)


@pytest.mark.parametrize("succeeds", [True, False])
def test_native_sign_in_status_is_pollable_and_redacts_errors(
    tmp_path, monkeypatch, vault, succeeds
):
    async def login(provider, **kwargs):
        assert provider == "github-copilot"
        kwargs["notify"]("Complete device sign-in in the provider browser")
        if not succeeds:
            raise RuntimeError("private-credential-from-provider")
        return {"state": "saved"}

    monkeypatch.setattr(module, "login", login)
    sign_ins = SignIns(Connections(AgentStore(tmp_path)))
    state = sign_ins.start("github-copilot", "operator-client-id")
    deadline = time.monotonic() + 3
    while state["state"] == "waiting" and time.monotonic() < deadline:
        time.sleep(0.01)
        state = sign_ins.get(state["id"])
    assert state["state"] == ("connected" if succeeds else "failed")
    assert "private-credential" not in json.dumps(state)
