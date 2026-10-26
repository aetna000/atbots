import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from atbots.platform import cloud_worker
from atbots.platform.scheduler import Scheduler
from atbots.platform.store import AgentStore


@pytest.mark.parametrize(
    "fail_checkpoint,exhausted", [(False, False), (True, False), (False, True)]
)
def test_cloud_writer_fence_checkpoint_failure_and_execution_allowance(
    tmp_path, monkeypatch, fail_checkpoint, exhausted
):
    store = AgentStore(tmp_path)
    store.create("researcher")
    deleted = []
    uploaded = []
    lease_contents = []

    def upload(payload, **kwargs):
        uploaded.append(kwargs)
        if fail_checkpoint:
            raise RuntimeError("fixture upload failure")

    state = SimpleNamespace(
        generation=7,
        metadata={"atbots_executions": "1" if exhausted else "0"},
        reload=lambda: None,
        download_as_bytes=lambda **kwargs: b"fixture",
        upload_from_string=upload,
    )
    lease = SimpleNamespace(
        generation=3,
        reload=lambda: None,
        upload_from_string=lambda payload, **kwargs: lease_contents.append(payload),
        download_as_text=lambda **kwargs: lease_contents[0],
        delete=lambda **kwargs: deleted.append(kwargs),
    )
    storage = SimpleNamespace(
        Client=lambda: SimpleNamespace(
            bucket=lambda name: SimpleNamespace(
                blob=lambda name: lease if name.endswith(".lease") else state
            )
        )
    )
    google = ModuleType("google")
    cloud = ModuleType("google.cloud")
    cloud.storage = storage
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setenv("ATBOTS_STATE_URI", "gs://fixture-bucket/state")
    monkeypatch.setenv("ATBOTS_STATE_KEY", "not-used-by-fixture")
    monkeypatch.setenv("ATBOTS_MAX_EXECUTIONS", "1")
    monkeypatch.setattr(cloud_worker, "unpack_state", lambda *args: store)
    monkeypatch.setattr(cloud_worker, "pack_state", lambda *args: b"checkpoint")
    monkeypatch.setattr(Scheduler, "tick", lambda *args: [])
    if fail_checkpoint or exhausted:
        with pytest.raises(RuntimeError):
            cloud_worker.main()
    else:
        cloud_worker.main()
    assert bool(deleted) == (not fail_checkpoint)
    if not exhausted:
        assert uploaded == [{"if_generation_match": 7}]
    else:
        assert not uploaded
    assert "owner" in json.loads(lease_contents[0])
