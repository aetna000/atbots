from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from atbots.platform.models import ModelBinding, RunLimits
from atbots.platform.store import AgentStore, StoreError


@pytest.fixture
def store(tmp_path):
    return AgentStore(tmp_path / "platform")


def test_agents_persist_and_are_isolated(store):
    a, b = store.create("researcher"), store.create("twitter")
    assert a.id != b.id
    assert store.workspace(a.name) != store.workspace(b.name)
    assert {p.name for p in store.workspace(a.name).iterdir()} == {
        "files",
        "browser",
        "locks",
    }
    store.save_turn(a.name, 0, b"[]", {"status": "completed"})
    reopened = AgentStore(store.root)
    assert reopened.get(a.name) == a
    assert reopened.history(a.name)[0] == 1
    assert reopened.history(b.name) == (0, b"[]")
    assert reopened.receipts(b.name) == []


@pytest.mark.parametrize(
    "name", ["../escape", "a/b", "auth", "agents", "UPPER", "", "-a", "a" * 49]
)
def test_invalid_names_have_no_agent_side_effects(store, name):
    with pytest.raises(ValueError):
        store.create(name)
    assert store.list() == []
    assert not (store.root / "workspaces").exists()


def test_duplicate_name_preserves_existing(store):
    first = store.create("researcher")
    with pytest.raises(StoreError, match="already exists"):
        store.create("researcher")
    assert store.get("researcher") == first


def test_revision_guards_and_stable_scope(store):
    a = store.create("researcher")
    updated = store.configure(
        a.name, expected_revision=1, instructions="New instructions"
    )
    assert updated.revision == 2 and updated.id == a.id
    with pytest.raises(StoreError, match="changed"):
        store.configure(a.name, expected_revision=1, state="paused")
    assert store.get(a.name) == updated
    with pytest.raises(StoreError, match="Unsupported"):
        store.configure(a.name, expected_revision=2, id="fake")


def test_history_compare_and_swap(store):
    store.create("researcher")
    store.save_turn("researcher", 0, b"[]", {"status": "completed"})
    with pytest.raises(StoreError, match="Conversation changed"):
        store.save_turn("researcher", 0, b"[]", {"status": "failed"})
    assert len(store.receipts("researcher")) == 1


def test_turn_lock_prevents_concurrent_config_or_turn(store):
    store.create("researcher")
    with store.turn_lock("researcher"):
        with pytest.raises(StoreError, match="busy"):  # noqa: SIM117 - deliberately test second acquisition under held lock
            with store.turn_lock("researcher"):
                pytest.fail("Second turn acquired a held lock")
        with pytest.raises(StoreError, match="busy"):
            store.configure("researcher", expected_revision=1, state="paused")


def test_remote_selection_needs_binding_and_agent_grant(store):
    with pytest.raises(ValidationError):
        ModelBinding(kind="chatgpt")
    remote = ModelBinding(kind="chatgpt", egress_class="remote")
    with pytest.raises(ValidationError):
        store.create("researcher", binding=remote)
    assert store.list() == []
    assert store.create(
        "researcher", binding=remote, remote_allowed=True
    ).remote_allowed


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.com",
        "http://localhost.evil.com",
        "https://user:password@example.com",
        "http://127.0.0.1?key=secret",
    ],
)
def test_endpoint_policy(endpoint):
    with pytest.raises(ValidationError):
        ModelBinding(endpoint=endpoint)


def test_limits_and_secret_references_are_strict():
    with pytest.raises(ValidationError):
        RunLimits(requests=True)
    with pytest.raises(ValidationError):
        ModelBinding(api_key="secret")
    with pytest.raises(ValidationError):
        ModelBinding(api_key_env="sk-not-an-env-reference")


def test_credential_bearing_instructions_are_not_persisted(store):
    with pytest.raises(ValidationError):
        store.create("researcher", instructions="My password is fixture-only")
    assert store.list() == []


def test_symlink_workspace_rejected(store, tmp_path):
    a = store.create("researcher")
    if os.name == "nt":
        pytest.skip("Creating symlinks requires an explicit Windows privilege")
    browser = store.workspace(a.name) / "browser"
    browser.rmdir()  # only this empty test fixture directory
    browser.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(StoreError, match="symlink"):
        store.workspace(a.name)


def test_private_registry_mode(store):
    if os.name != "nt":
        assert store.database.stat().st_mode & 0o777 == 0o600


def test_future_schema_is_not_silently_downgraded(store):
    with store.connect() as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(StoreError, match="newer"):
        AgentStore(store.root)
    with store.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99
