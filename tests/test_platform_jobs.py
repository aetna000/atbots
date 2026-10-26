import time
from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel

from atbots.platform.control import ControlPlan, ControlRoom
from atbots.platform.jobs import Operations
from atbots.platform.store import AgentStore, StoreError
from atbots.platform.worker import execute


def setup(tmp_path):
    store = AgentStore(tmp_path)
    store.create("researcher")
    return store, Operations(store)


def test_idempotency_leases_and_stale_fencing(tmp_path):
    store, ops = setup(tmp_path)
    job = ops.submit("researcher", "Read the project", idempotency="one")
    assert (
        ops.submit("researcher", "Read the project", idempotency="one")["id"]
        == job["id"]
    )
    with pytest.raises(StoreError):
        ops.submit("researcher", "Different project", idempotency="one")
    token = ops.claim(job["id"])
    with pytest.raises(StoreError):
        ops.claim(job["id"])
    with store.connect() as db:
        db.execute("UPDATE jobs SET lease=? WHERE id=?", (time.time() - 1, job["id"]))
    assert ops.get(job["id"])["stale"]
    assert ops.reconcile_stale() == 1
    with pytest.raises(StoreError, match="fenced"):
        ops.finish(job["id"], token, "replied", {"answer": "late"})
    assert ops.get(job["id"])["status"] == "needs_review"


def test_worker_result_survives_reopen_not_verified_by_exit(tmp_path):
    _store, ops = setup(tmp_path)
    job = ops.submit("researcher", "Read project")

    class Fixture:
        def __init__(self, *args, **kwargs):
            pass

        def chat(self, prompt):
            return SimpleNamespace(text="Fixture output", at="fixture", requests=1)

    execute(ops, job["id"], Fixture)
    result = Operations(AgentStore(tmp_path)).get(job["id"])
    assert result["status"] == "replied"
    assert result["result"]["answer"] == "Fixture output"
    assert not result["result"]["objective_verified"]


def test_pause_resume_cancel_and_failure(tmp_path):
    _, ops = setup(tmp_path)
    job = ops.submit("researcher", "Read project")
    assert ops.action(job["id"], "pause")["status"] == "paused"
    assert ops.action(job["id"], "resume")["status"] == "queued"
    assert ops.action(job["id"], "cancel")["status"] == "cancelled"
    with pytest.raises(StoreError):
        ops.claim(job["id"])


def test_only_one_active_job_per_agent(tmp_path):
    _, ops = setup(tmp_path)
    one = ops.submit("researcher", "First")
    two = ops.submit("researcher", "Second")
    token = ops.claim(one["id"])
    with pytest.raises(StoreError, match="remains queued"):
        ops.claim(two["id"])
    assert ops.get(two["id"])["status"] == "queued"
    ops.finish(one["id"], token, "replied", {"answer": "done"})
    assert ops.claim(two["id"])


def test_approval_survives_control_room_restart_and_is_single_use(tmp_path):
    store, _ = setup(tmp_path)
    room = ControlRoom(store, model=TestModel())
    proposal = room.dispatch(ControlPlan(action="create", name="other"))
    reopened = ControlRoom(AgentStore(tmp_path), model=TestModel())
    assert reopened.approve(proposal["approval_required"])["applied"]["name"] == "other"
    with pytest.raises(StoreError):
        room.approve(proposal["approval_required"])


def test_memory_approval_invalidated_by_changed_record(tmp_path):
    from atbots.platform.memory import AtMemMemory

    store, _ = setup(tmp_path)
    memory = AtMemMemory(store, "researcher")
    record = memory.remember("I prefer concise technical answers")["record_ids"][0]
    room = ControlRoom(store, model=TestModel())
    from atbots.platform.environment import AgentEnvironment

    proposal = AgentEnvironment(store, "researcher", memory).request_memory_change(
        "forget", record
    )
    memory.correct(record, "I prefer detailed technical answers")
    with pytest.raises(StoreError, match="Memory changed"):
        room.approve(proposal["approval_required"])
