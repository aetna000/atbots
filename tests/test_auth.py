"""Offline native auth and inference wiring tests; no real credential access."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from atbots import auth
from atbots.cli import main
from atbots.config import AtBotConfig, ProviderConfig
from atbots.providers.authenticated import AuthenticatedProvider
from atbots.providers.router import ModelRouter


class MemoryStore:
    def __init__(self):
        self.data = {}

    def load(self, provider, profile):
        return self.data.get((provider, profile))

    def save(self, provider, profile, credentials):
        self.data[provider, profile] = {
            "version": 1,
            "issued_at": time.time(),
            "credentials": asdict(credentials),
        }

    def delete(self, provider, profile):
        return self.data.pop((provider, profile), None) is not None


@pytest.fixture(autouse=True)
def isolated_auth(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "DEFAULT_ROOT", tmp_path / "atbots")


@pytest.fixture
def store(monkeypatch):
    target = MemoryStore()
    monkeypatch.setattr(auth, "CredentialStore", lambda: target)
    monkeypatch.setattr(
        "atbots.providers.authenticated.CredentialStore", lambda: target
    )
    return target


def credentials(scope="chatgpt.tokens.use.direct"):
    native = auth.native_module("chatgpt")
    return native.OpenAIChatGPTCredentials(
        client_id="test-client",
        access_token="access-secret",
        refresh_token="refresh-secret",
        id_token="identity-secret",
        scope=scope,
    )


def row(kind="chatgpt", **kwargs):
    return ProviderConfig(
        name="account", kind=kind, model="test-model", egress_class="remote", **kwargs
    )


@pytest.mark.parametrize("profile", ["", "../outside", "a/b", "a" * 65, "has space"])
def test_profile_validation(profile):
    with pytest.raises(auth.AuthError):
        auth.validate_profile("chatgpt", profile)


def test_optional_import_guidance(monkeypatch):
    monkeypatch.setattr(
        auth.importlib,
        "import_module",
        lambda _: (_ for _ in ()).throw(ImportError("secret")),
    )
    with pytest.raises(auth.AuthError, match=r"atbots\[auth\]") as exc:
        auth.native_module("chatgpt")
    assert "secret" not in str(exc.value)


@pytest.mark.parametrize("kind", ["chatgpt", "github-copilot", "anthropic"])
def test_account_kinds_require_remote_declaration(kind):
    with pytest.raises(ValueError, match="egress_class"):
        ProviderConfig(kind=kind)


def test_status_redacted_and_not_entitlement(store):
    store.save("chatgpt", "default", credentials())
    result = auth.auth_status("chatgpt")
    assert result["state"] == "saved"
    assert result["inference_access"] == "unverified"
    assert result["live_checked"] is False
    assert "secret" not in json.dumps(result)
    assert auth.auth_status("chatgpt", "other")["state"] == "signed_out"


def test_identity_is_not_plan_permission(store):
    store.save("chatgpt", "default", credentials("openid profile"))
    assert auth.auth_status("chatgpt")["state"] == "identity_only"
    source = auth.chatgpt_source("default", store)
    with pytest.raises(auth.AuthError, match="plan usage"):
        asyncio.run(source.load())


def test_rotation_uses_native_source_and_persists(store):
    source = auth.chatgpt_source("default", store)
    store.save("chatgpt", "default", credentials())
    assert asyncio.run(source.load()).refresh_token == "refresh-secret"
    refreshed = credentials()
    refreshed.refresh_token = "rotated-secret"
    asyncio.run(source.save(refreshed))
    assert asyncio.run(source.load()).refresh_token == "rotated-secret"


@pytest.mark.parametrize(
    "age,expires,state",
    [
        (100, 50, "relogin_required"),
        (0, 600, "saved"),
        (0, float("nan"), "relogin_required"),
        (0, True, "relogin_required"),
    ],
)
def test_copilot_expiry_is_not_renewal(age, expires, state, store):
    store.data["github-copilot", "default"] = {
        "issued_at": time.time() - age,
        "credentials": {"access_token": "copilot-secret", "expires_in": expires},
    }
    assert auth.auth_status("github-copilot")["state"] == state


def test_logout_only_own_profile(store):
    store.save("chatgpt", "default", credentials())
    store.save("chatgpt", "other", credentials())
    result = auth.logout("chatgpt")
    assert result["removed"] and not result["remote_revoked"]
    assert auth.auth_status("chatgpt")["state"] == "signed_out"
    assert auth.auth_status("chatgpt", "other")["state"] == "saved"
    assert not auth.logout("chatgpt")["removed"]


def test_chatgpt_browser_flow_uses_own_registration_and_saves(
    monkeypatch, store, capsys
):
    native = auth.native_module("chatgpt")
    store.save("chatgpt", "default", credentials("openid"))
    params = {}

    class Flow:
        def __init__(self, **kwargs):
            params.update(kwargs)

        def authorization_url(self, **kwargs):
            assert kwargs == {"extra_params": {"prompt": "consent"}}
            return "https://auth.openai.com/authorize?id_token_hint=identity-secret"

        async def exchange_code_from_callback(self):
            return credentials()

    monkeypatch.setattr(native, "OpenAIChatGPTOAuthFlow", Flow)
    urls = []
    result = asyncio.run(
        auth.login("chatgpt", open_browser=lambda u: urls.append(u) or True)
    )
    assert result["state"] == "saved"
    assert params["app_name"] == "AtBots" and params["client_id"] == "test-client"
    assert urls and "secret" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "error", [RuntimeError("access-secret"), asyncio.TimeoutError()]
)
def test_login_error_never_prints_tokens(monkeypatch, store, error):
    native = auth.native_module("chatgpt")

    class Flow:
        def __init__(self, **kwargs):
            pass

        def authorization_url(self, **kwargs):
            return "https://auth.openai.com/authorize"

        async def exchange_code_from_callback(self):
            raise error

    monkeypatch.setattr(native, "OpenAIChatGPTOAuthFlow", Flow)
    with pytest.raises(auth.AuthError) as exc:
        asyncio.run(auth.login("chatgpt", open_browser=lambda _: True))
    assert "access-secret" not in str(exc.value)
    assert store.data == {}


def test_cancelled_login_does_not_save(monkeypatch, store):
    native = auth.native_module("chatgpt")

    class Flow:
        def __init__(self, **kwargs):
            pass

        def authorization_url(self, **kwargs):
            return "https://auth.openai.com/authorize"

        async def exchange_code_from_callback(self):
            raise asyncio.CancelledError()

    monkeypatch.setattr(native, "OpenAIChatGPTOAuthFlow", Flow)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(auth.login("chatgpt", open_browser=lambda _: True))
    assert not store.data


def test_copilot_requires_own_client_id(store):
    with pytest.raises(auth.AuthError, match="own device-enabled"):
        asyncio.run(auth.login("github-copilot"))
    assert not store.data


def test_copilot_device_flow(monkeypatch, store, capsys):
    native = auth.native_module("github-copilot")
    captured = {}

    class Flow:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def start(self):
            return SimpleNamespace(
                verification_uri="https://github.com/login/device",
                user_code="TEST-CODE",
            )

        async def wait_for_authorization(self):
            return native.GitHubCopilotCredentials(
                access_token="copilot-secret", token_type="bearer", scope=""
            )

    monkeypatch.setattr(native, "GitHubCopilotOAuthFlow", Flow)
    result = asyncio.run(auth.login("github-copilot", client_id="own-application"))
    assert result["state"] == "saved" and result["inference_access"] == "unverified"
    assert captured == {"client_id": "own-application"}
    output = capsys.readouterr().out
    assert "TEST-CODE" in output and "copilot-secret" not in output


def test_native_keychain_roundtrip(monkeypatch):
    import keyring

    data = {}
    Backend = type(
        "Keyring",
        (),
        {
            "__module__": "keyring.backends.macOS",
            "priority": 5,
            "get_password": lambda _, s, k: data.get((s, k)),
            "set_password": lambda _, s, k, v: data.__setitem__((s, k), v),
            "delete_password": lambda _, s, k: data.pop((s, k)),
        },
    )
    monkeypatch.setattr(keyring, "get_keyring", lambda: Backend())
    store = auth.CredentialStore()
    store.save("chatgpt", "default", credentials())
    assert store.load("chatgpt", "default")["credentials"]["client_id"] == "test-client"
    assert store.delete("chatgpt", "default") and not store.delete("chatgpt", "default")


def test_windows_large_credentials_rotation_and_failure(monkeypatch):
    import keyring

    data = {}
    class Backend:
        __module__ = "keyring.backends.Windows"
        priority = 5
        fail = False

        def get_password(self, service, account):
            return data.get((service, account))

        def set_password(self, service, account, value):
            assert len(value.encode("utf-16-le")) <= 2560
            if self.fail and service == auth.SERVICE:
                raise RuntimeError("secret")
            data[service, account] = value

        def delete_password(self, service, account):
            del data[service, account]

    backend = Backend()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    store = auth.CredentialStore()
    original = credentials()
    original.access_token = "a" * 8000 + "😀"
    store.save("chatgpt", "default", original)
    assert store.load("chatgpt", "default")["credentials"]["access_token"] == original.access_token
    old_data = data.copy()
    backend.fail = True
    with pytest.raises(auth.AuthError):
        store.save("chatgpt", "default", credentials())
    assert data == old_data
    backend.fail = False
    store.save("chatgpt", "default", credentials())
    assert store.load("chatgpt", "default")["credentials"]["access_token"] == "access-secret"
    assert store.delete("chatgpt", "default")
    assert not data


def test_windows_reads_legacy_credential_and_rejects_missing_chunk(monkeypatch):
    import keyring

    data = {(auth.SERVICE, "chatgpt:default"): json.dumps({"version": 1, "credentials": {"access_token": "old"}})}
    Backend = type("Keyring", (), {
        "__module__": "keyring.backends.Windows", "priority": 5,
        "get_password": lambda _, s, k: data.get((s, k)),
        "set_password": lambda _, s, k, v: data.__setitem__((s, k), v),
        "delete_password": lambda _, s, k: data.pop((s, k)),
    })
    monkeypatch.setattr(keyring, "get_keyring", lambda: Backend())
    store = auth.CredentialStore()
    assert store.load("chatgpt", "default")["credentials"]["access_token"] == "old"
    store.save("chatgpt", "default", credentials())
    manifest = json.loads(data[auth.SERVICE, "chatgpt:default"])
    del data[store._chunk_services("chatgpt:default", manifest)[0], "chatgpt:default"]
    with pytest.raises(auth.AuthError, match="Cannot read"):
        store.load("chatgpt", "default")


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows Credential Manager")
@pytest.mark.parametrize("provider", ["chatgpt", "github-copilot"])
def test_windows_real_credential_manager_large_synthetic_authorization(provider):
    from dataclasses import dataclass

    @dataclass
    class SyntheticCredentials:
        access_token: str
        refresh_token: str

    profile = "test-" + uuid.uuid4().hex
    store = auth.CredentialStore()
    assert type(store.backend).__module__ == "keyring.backends.Windows"
    value = SyntheticCredentials("a" * 8000, "b" * 8000)
    try:
        store.save(provider, profile, value)
        assert store.load(provider, profile)["credentials"] == asdict(value)
        value.access_token = "rotated-" + "c" * 6000
        store.save(provider, profile, value)
        assert store.load(provider, profile)["credentials"] == asdict(value)
    finally:
        store.delete(provider, profile)


@pytest.mark.parametrize(
    "module", ["keyrings.alt.file", "keyring.backends.chainer", "keyring.backends.fail"]
)
def test_plaintext_or_chained_backend_rejected(monkeypatch, module):
    import keyring

    Backend = type("Bad", (), {"__module__": module, "priority": 99})
    monkeypatch.setattr(keyring, "get_keyring", lambda: Backend())
    with pytest.raises(auth.AuthError, match="OS keychain"):
        auth.CredentialStore()


def test_keychain_write_failure_redacted(monkeypatch):
    import keyring

    def fail(*args):
        raise RuntimeError("refresh-secret")

    Backend = type(
        "Keyring",
        (),
        {"__module__": "keyring.backends.macOS", "priority": 5, "set_password": fail},
    )
    monkeypatch.setattr(keyring, "get_keyring", lambda: Backend())
    with pytest.raises(auth.AuthError) as exc:
        auth.CredentialStore().save("chatgpt", "default", credentials())
    assert "refresh-secret" not in str(exc.value)


def test_profile_lock_rejects_concurrent_request():
    with auth.profile_lock("chatgpt", "default"):  # noqa: SIM117 - outer lock must precede competing acquire
        with pytest.raises(auth.AuthError, match="busy"):
            with auth.profile_lock("chatgpt", "default", timeout=0):
                pytest.fail("must not enter")


def test_router_preserves_remote_and_sensitive_policy(store):
    store.save("chatgpt", "default", credentials())
    config = AtBotConfig(providers=[row()])
    router = ModelRouter(config)
    assert router.select(remote=True).egress_class == "local"
    config.remote_egress_allowed = True
    assert router.select(remote=True).name == "account"
    assert router.select(remote=False).egress_class == "local"
    assert router.select(remote=True, sensitivity="restricted").egress_class == "local"
    status = router.status()[0]
    assert status["inference_access"] == "unverified"
    assert "secret" not in json.dumps(status)


def test_missing_subscription_never_falls_through_to_another_paid_provider(store):
    config = AtBotConfig(
        providers=[row(), row("github-copilot")], remote_egress_allowed=True
    )
    with pytest.raises(auth.AuthError, match="signed_out"):
        ModelRouter(config).select(remote=True)


def test_request_errors_redacted_no_retry(monkeypatch, store):
    provider = AuthenticatedProvider(row(), capability_refs=[], retries=2)
    calls = []

    async def fail(*args):
        calls.append(True)
        raise RuntimeError("Authorization: access-secret")

    monkeypatch.setattr(provider, "_invoke", fail)
    with pytest.raises(auth.AuthError) as exc:
        provider.complete(system="rules", prompt="hi")
    assert len(calls) == 1 and "access-secret" not in str(exc.value)


def test_cli_auth_does_not_load_config_or_companion(monkeypatch, store, capsys):
    monkeypatch.setattr(
        "atbots.cli.load_config", lambda *args: pytest.fail("auth must not load config")
    )
    assert main(["auth", "status", "chatgpt"]) == 1
    assert json.loads(capsys.readouterr().out)["state"] == "signed_out"


def test_cli_anthropic_oauth_is_honestly_unsupported(capsys):
    assert main(["auth", "login", "anthropic"]) == 2
    assert "not supported" in capsys.readouterr().err


def test_anthropic_api_key_readiness(monkeypatch):
    provider = AuthenticatedProvider(
        row("anthropic", api_key_env="TEST_ANTHROPIC_API_KEY"),
        capability_refs=[],
        retries=1,
    )
    monkeypatch.delenv("TEST_ANTHROPIC_API_KEY", raising=False)
    assert not provider.available()
    monkeypatch.setenv("TEST_ANTHROPIC_API_KEY", "fake-api-key")
    assert provider.available()


def test_old_config_remains_default_local():
    config = AtBotConfig.from_dict({"format": "atbot-config-v1"})
    assert config.providers[0].kind == "ollama"
    assert config.providers[0].auth_profile == "default"
    assert not config.remote_egress_allowed


@pytest.mark.parametrize("fail_save", [False, True])
def test_native_chatgpt_401_refresh_persists_before_replay(
    store, monkeypatch, fail_save
):
    import httpx2

    native = auth.native_module("chatgpt")
    store.save("chatgpt", "default", credentials())
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.host == "auth.openai.com":
            assert b"refresh_token=refresh-secret" in request.content
            return httpx2.Response(
                200,
                json={
                    "access_token": "new-access-secret",
                    "refresh_token": "new-refresh-secret",
                    "token_type": "Bearer",
                },
            )
        assert request.url.host == "api.openai.com"
        if request.headers["Authorization"] == "Bearer access-secret":
            return httpx2.Response(
                401,
                json={"error": {"message": "expired", "type": "invalid_request_error"}},
            )
        assert request.headers["Authorization"] == "Bearer new-access-secret"
        assert (
            store.load("chatgpt", "default")["credentials"]["refresh_token"]
            == "new-refresh-secret"
        )
        return httpx2.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "model": "test-model",
                "output": [],
                "status": "completed",
            },
        )

    if fail_save:

        def reject_save(*args):
            raise auth.AuthError("Cannot persist authentication")

        monkeypatch.setattr(store, "save", reject_save)

    async def run():
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            provider = native.OpenAIChatGPTProvider(
                credential_source=auth.chatgpt_source("default", store),
                http_client=client,
            )
            async with provider:
                return await provider.client.responses.create(
                    model="test-model", input="test"
                )

    if fail_save:
        with pytest.raises(native.CredentialsPersistenceError):
            asyncio.run(run())
        assert len(calls) == 2  # rotated token was never used in another inference
    else:
        assert asyncio.run(run()).id == "resp_test"
        assert len(calls) == 3


@pytest.mark.parametrize("kind", ["chatgpt", "github-copilot", "anthropic"])
def test_real_native_model_and_structured_output_over_mock_http(
    monkeypatch, store, kind
):
    import httpx2
    from pydantic import BaseModel

    class Answer(BaseModel):
        answer: str

    store.save("chatgpt", "default", credentials())
    store.data["github-copilot", "default"] = {
        "issued_at": time.time(),
        "credentials": {"access_token": "copilot-secret"},
    }
    monkeypatch.setenv("TEST_ANTHROPIC_API_KEY", "fake-anthropic-key")
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        if kind == "chatgpt":
            assert request.url.host == "api.openai.com"
            assert request.headers["Authorization"] == "Bearer access-secret"
            response = {
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "test-model",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"answer":"ok"}',
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            }
        elif kind == "github-copilot":
            assert request.url.host == "api.githubcopilot.com"
            assert request.headers["Authorization"] == "Bearer copilot-secret"
            response = {
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"answer":"ok"}'},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            }
        else:
            assert request.url.host == "api.anthropic.com"
            assert (
                request.headers.get("x-api-key") == "fake-anthropic-key"
                or request.headers.get("Authorization") == "Bearer fake-anthropic-key"
            )
            response = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "test-model",
                "content": [{"type": "text", "text": '{"answer":"ok"}'}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 4},
            }
        if kind == "chatgpt" and body.get("stream"):
            item = response["output"][0]
            events = [
                {"type": "response.created", "response": {**response, "output": []}},
                {
                    "type": "response.output_item.added",
                    "output_index": 0,
                    "item": {**item, "content": []},
                },
                {
                    "type": "response.content_part.added",
                    "output_index": 0,
                    "item_id": item["id"],
                    "content_index": 0,
                    "part": {"type": "output_text", "text": "", "annotations": []},
                },
                {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "item_id": item["id"],
                    "content_index": 0,
                    "delta": '{"answer":"ok"}',
                },
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {"type": "response.completed", "response": response},
            ]
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content="".join(
                    f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events
                ),
            )
        return httpx2.Response(200, json=response)

    if kind == "anthropic":
        from pydantic_ai.providers import anthropic as native

        name = "AnthropicProvider"
    else:
        native = auth.native_module(kind)
        name = "OpenAIChatGPTProvider" if kind == "chatgpt" else "GitHubCopilotProvider"
    original = getattr(native, name)
    clients = []

    def factory(**kwargs):
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        clients.append(client)
        return original(http_client=client, **kwargs)

    monkeypatch.setattr(native, name, factory)
    provider = AuthenticatedProvider(
        row(
            kind, api_key_env="TEST_ANTHROPIC_API_KEY" if kind == "anthropic" else None
        ),
        capability_refs=[],
        retries=1,
    )
    try:
        try:
            result = provider.complete(
                system="Reply using the requested JSON shape.",
                prompt="Return ok",
                output_type=Answer,
            )
        except auth.AuthError as exc:
            # This test uses only synthetic credentials and intercepted HTTP.
            raise AssertionError(
                f"Mock native adapter failure: {exc.__context__}; requests="
                f"{[(str(r.url), list(r.headers)) for r in requests]}"
            ) from exc
        assert result.structured == {"answer": "ok"}
        assert (result.input_tokens, result.output_tokens) == (10, 4)
        assert len(requests) == 1
    finally:
        for client in clients:
            asyncio.run(client.aclose())
