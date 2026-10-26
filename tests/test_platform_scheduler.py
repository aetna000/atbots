from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfoNotFoundError

import pytest

from atbots.platform.scheduler import Scheduler
from atbots.platform.store import AgentStore


def setup(tmp_path):
    store = AgentStore(tmp_path)
    store.create("researcher")
    return store, Scheduler(store)


def test_oneshot_restart_idempotency_and_missed_policy(tmp_path):
    _store, scheduler = setup(tmp_path)
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    one = scheduler.create(
        "researcher", "Write a briefing", at=now + timedelta(minutes=1), now=now
    )
    reopened = Scheduler(AgentStore(tmp_path))
    assert len(reopened.tick(now=now + timedelta(minutes=1))) == 1
    assert reopened.tick(now=now + timedelta(minutes=1)) == []
    assert not reopened.get(one["id"])["enabled"]
    scheduler.create(
        "researcher", "Missed briefing", at=now + timedelta(minutes=1), now=now
    )
    assert scheduler.tick(now=now + timedelta(hours=1)) == []


def test_cron_timezone_preview_and_overlap(tmp_path):
    _, scheduler = setup(tmp_path)
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    plan = scheduler.create(
        "researcher",
        "Weekly briefing",
        cron="0 9 * * mon",
        zone="Australia/Sydney",
        now=now,
    )
    preview = scheduler.preview(plan["id"])
    assert len(preview["occurrences_utc"]) == 5
    fire = datetime.fromisoformat(preview["occurrences_utc"][0])
    assert len(scheduler.tick(now=fire)) == 1
    next_fire = datetime.fromisoformat(scheduler.get(plan["id"])["next"])
    assert scheduler.tick(now=next_fire) == []
    scheduler.action(plan["id"], "pause")
    assert not scheduler.get(plan["id"])["enabled"]


def test_naive_time_and_bad_timezone_refused(tmp_path):
    _, scheduler = setup(tmp_path)
    with pytest.raises(ValueError):
        scheduler.create("researcher", "Do work", at="2027-01-01T09:00:00")
    with pytest.raises(ZoneInfoNotFoundError):
        scheduler.create("researcher", "Do work", cron="* * * * *", zone="not-a-zone")


def test_paused_agent_cannot_launch_previously_queued_jobs(tmp_path, monkeypatch):
    from atbots.platform.jobs import Operations
    from atbots.platform.store import StoreError

    store, scheduler = setup(tmp_path)
    job = scheduler.operations.submit("researcher", "Write a report")
    store.configure("researcher", expected_revision=1, state="paused")
    launched = []
    monkeypatch.setattr(
        scheduler.operations, "launch", lambda identity: launched.append(identity)
    )
    scheduler.run_once()
    assert not launched
    with pytest.raises(StoreError, match="paused"):
        Operations(store).claim(job["id"])
    with pytest.raises(StoreError, match="paused"):
        Operations(store).launch(job["id"])
    store.configure("researcher", expected_revision=2, state="active")
    scheduler.run_once()
    assert launched == [job["id"]]


def test_dst_gap_skipped_fold_has_distinct_occurrences_and_edit(tmp_path):
    from atbots.platform.scheduler import aware

    _, scheduler = setup(tmp_path)
    spring = scheduler._next(
        "30 2 * * *", "America/New_York", aware("2027-03-14T00:00:00Z")
    )
    assert spring == aware("2027-03-15T06:30:00Z")
    first = scheduler._next(
        "30 1 * * *", "America/New_York", aware("2026-11-01T00:00:00Z")
    )
    second = scheduler._next("30 1 * * *", "America/New_York", first)
    assert (second - first).total_seconds() == 3600
    plan = scheduler.create(
        "researcher",
        "Before",
        at="2027-01-02T00:00:00Z",
        now=aware("2027-01-01T00:00:00Z"),
    )
    edited = scheduler.edit(
        plan["id"],
        "After",
        cron="0 9 * * *",
        zone="Europe/Berlin",
        now=aware("2027-01-01T00:00:00Z"),
    )
    assert edited["id"] == plan["id"] and edited["objective"] == "After"
