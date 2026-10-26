import pytest
from cryptography.fernet import Fernet, InvalidToken

from atbots.platform.deployment import (
    CloudPlan,
    CloudRun,
    export_definition,
    import_definition,
    pack_state,
    restore_cloud_state,
    stage_cloud_state,
    unpack_state,
)
from atbots.platform.memory import AtMemMemory
from atbots.platform.models import ModelBinding
from atbots.platform.store import AgentStore, StoreError


def test_manifest_no_private_data_and_import_grants(tmp_path):
    store = AgentStore(tmp_path / "source")
    store.create("researcher")
    AtMemMemory(store, "researcher").remember("I prefer concise technical answers")
    manifest = export_definition(store, "researcher")
    assert "concise technical" not in str(manifest)
    target = AgentStore(tmp_path / "target")
    assert import_definition(target, manifest).id == store.get("researcher").id
    with pytest.raises(StoreError):
        import_definition(target, manifest)
    store.create(
        "remote",
        binding=ModelBinding(kind="chatgpt", egress_class="remote"),
        remote_allowed=True,
    )
    with pytest.raises(PermissionError):
        import_definition(target, export_definition(store, "remote"))


def test_encrypted_state_restore_preserves_memory_not_browser(tmp_path):
    store = AgentStore(tmp_path / "source")
    store.create("researcher")
    memory = AtMemMemory(store, "researcher")
    memory.remember("I prefer concise technical answers")
    (store.workspace("researcher") / "browser" / "cookie-fixture").write_text(
        "private browser fixture"
    )
    key = Fernet.generate_key()
    blob = pack_state(store, "researcher", key)
    assert b"concise technical" not in blob
    restored = unpack_state(blob, tmp_path / "restored", key)
    assert (
        "concise technical"
        in AtMemMemory(restored, "researcher")
        .context("concise technical", egress="local")
        .text
    )
    assert not (
        restored.workspace("researcher") / "browser" / "cookie-fixture"
    ).exists()
    with pytest.raises(InvalidToken):
        unpack_state(blob, tmp_path / "wrong", Fernet.generate_key())


def test_cloud_argv_pinned_image_and_explicit_grant_no_shell():
    data = {
        "project": "project-123",
        "region": "us-central1",
        "job": "researcher",
        "image": "us-docker.pkg.dev/project-123/repo/atbots@sha256:" + "a" * 64,
        "state_uri": "gs://private-bucket/state/researcher",
        "service_account": "worker@project-123.iam.gserviceaccount.com",
        "state_key_secret": "state-key:1",
        "spending_grant_usd": 1.0,
        "state_transfer_authorized": True,
        "acknowledges_not_hard_billing_cap": True,
    }
    plan = CloudPlan(**data)
    argv = CloudRun().command(plan, "deploy")
    assert "--max-retries=0" in argv and plan.image in argv
    with pytest.raises(ValueError):
        CloudPlan(**{**data, "state_transfer_authorized": False})
    with pytest.raises(ValueError):
        CloudPlan(**{**data, "image": "image:latest"})


def test_cloud_state_handoff_fences_source_and_activates_only_destination(tmp_path):
    from types import SimpleNamespace

    store = AgentStore(tmp_path / "source")
    definition = store.create(
        "researcher",
        binding=ModelBinding(
            kind="openai-compatible",
            model="operator-model",
            endpoint="https://api.example.invalid/v1",
            api_key_env="MODEL_KEY",
            egress_class="remote",
        ),
        remote_allowed=True,
    )
    store.configure("researcher", expected_revision=definition.revision, state="paused")
    plan = CloudPlan(
        project="project-123",
        region="us-central1",
        job="researcher",
        image="repo/image@sha256:" + "a" * 64,
        state_uri="gs://private-bucket/state/researcher",
        service_account="worker@project-123.iam.gserviceaccount.com",
        state_key_secret="state-key:1",
        model_secret_refs={"MODEL_KEY": "model-key:1"},
        spending_grant_usd=1,
        state_transfer_authorized=True,
        acknowledges_not_hard_billing_cap=True,
    )
    captured = []
    blob = SimpleNamespace(
        upload_from_string=lambda payload, **kwargs: captured.append((payload, kwargs)),
        reload=lambda: None,
        generation=7,
    )
    client = SimpleNamespace(bucket=lambda _: SimpleNamespace(blob=lambda _: blob))
    key = Fernet.generate_key()
    result = stage_cloud_state(store, "researcher", plan, key, client=client)
    assert result["generation"] == "7" and captured[0][1]["if_generation_match"] == 0
    assert store.get("researcher").state == "paused"
    with pytest.raises(StoreError, match="fenced"):
        store.configure("researcher", expected_revision=2, state="active")
    restored = unpack_state(captured[0][0], tmp_path / "destination", key)
    assert restored.get("researcher").state == "active"


def test_archive_preserves_job_event_trail(tmp_path):
    from atbots.platform.jobs import Operations

    store = AgentStore(tmp_path / "source")
    store.create("researcher")
    ops = Operations(store)
    job = ops.submit("researcher", "Read project")
    ops.action(job["id"], "cancel")
    key = Fernet.generate_key()
    restored = unpack_state(
        pack_state(store, "researcher", key), tmp_path / "destination", key
    )
    assert Operations(restored).get(job["id"])["events"][0]["kind"] == "queued"


def test_restore_cloud_claims_remote_lease_and_returns_paused_local_owner(tmp_path):
    from types import SimpleNamespace

    source = AgentStore(tmp_path / "source")
    source.create("researcher")
    key = Fernet.generate_key()
    payload = pack_state(source, "researcher", key)
    claims = []
    lease = SimpleNamespace(
        upload_from_string=lambda payload, **kwargs: claims.append(kwargs)
    )
    state = SimpleNamespace(
        generation=9, reload=lambda: None, download_as_bytes=lambda **kwargs: payload
    )
    client = SimpleNamespace(
        bucket=lambda name: SimpleNamespace(
            blob=lambda path: lease if path.endswith(".lease") else state
        )
    )
    plan = SimpleNamespace(project="fixture", state_uri="gs://fixture/state")
    result = restore_cloud_state(plan, key, tmp_path / "destination", client=client)
    assert claims == [{"if_generation_match": 0}]
    assert result["state"] == "paused" and result["cloud_fence"].startswith(
        "local-handoff-"
    )
    assert AgentStore(tmp_path / "destination").get("researcher").state == "paused"


def test_cloud_trigger_targets_jobs_api_with_oauth_and_no_retry():
    from types import SimpleNamespace

    plan = SimpleNamespace(
        project="fixture",
        region="us-central1",
        job="researcher",
        cron="0 9 * * *",
        timezone="UTC",
        service_account="fixture@example.invalid",
    )
    argv = CloudRun().command(plan, "schedule")
    assert (
        "https://run.googleapis.com/v2/projects/fixture/locations/us-central1/jobs/researcher:run"
        in argv
    )
    assert "--oauth-service-account-email" in argv and "--max-retry-attempts=0" in argv
