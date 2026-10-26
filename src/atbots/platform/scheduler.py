"""Durable schedule intent; APScheduler computes calendar occurrences."""

import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from atbots.platform.jobs import Operations
from atbots.platform.memory import screen_message
from atbots.platform.store import AgentStore, StoreError


def aware(value):
    result = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Schedule time must include a timezone offset")
    return result.astimezone(timezone.utc)


class Scheduler:
    def __init__(self, store: AgentStore):
        self.store, self.operations = store, Operations(store)
        with store.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY,agent TEXT NOT NULL,objective TEXT NOT NULL,cron TEXT,zone TEXT NOT NULL,next TEXT NOT NULL,missed TEXT NOT NULL,overlap TEXT NOT NULL,enabled INTEGER NOT NULL)"
            )

    def create(
        self,
        name,
        objective,
        *,
        at=None,
        cron=None,
        zone="UTC",
        missed="skip",
        overlap="skip",
        now=None,
    ):
        self.store.get(name)
        screen_message(objective)
        if not objective.strip() or len(objective) > 32000:
            raise ValueError("Schedule requires a bounded objective")
        if (
            bool(at) == bool(cron)
            or missed not in {"skip", "catch_up_once"}
            or overlap not in {"skip", "queue"}
        ):
            raise ValueError(
                "Choose one-shot at or cron, explicit missed and overlap policy"
            )
        ZoneInfo(zone)
        current = aware(now or datetime.now(timezone.utc))
        next_fire = aware(at) if at else self._next(cron, zone, current)
        if next_fire <= current:
            raise ValueError("Initial schedule must be in the future")
        identity = uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO schedules VALUES (?,?,?,?,?,?,?,?,1)",
                (
                    identity,
                    name,
                    objective,
                    cron,
                    zone,
                    next_fire.isoformat(),
                    missed,
                    overlap,
                ),
            )
        return self.get(identity)

    def _next(self, cron, zone, after):
        try:
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            raise RuntimeError(
                'Install scheduling support: python -m pip install "atbots[schedule]"'
            ) from None
        trigger = CronTrigger.from_crontab(cron, timezone=ZoneInfo(zone))
        fire = trigger.get_next_fire_time(None, after + timedelta(microseconds=1))
        # CronTrigger can return an imaginary spring-forward wall time. Skip
        # that occurrence rather than silently running it an hour later.
        for _ in range(8):
            if fire is None or fire.astimezone(timezone.utc).astimezone(
                ZoneInfo(zone)
            ).replace(tzinfo=None) == fire.replace(tzinfo=None):
                break
            fire = trigger.get_next_fire_time(
                fire, aware(fire) + timedelta(microseconds=1)
            )
        if fire is None:
            raise ValueError("Cron expression has no next occurrence")
        return aware(fire)

    def edit(
        self,
        identity,
        objective,
        *,
        at=None,
        cron=None,
        zone="UTC",
        missed="skip",
        overlap="skip",
        now=None,
    ):
        screen_message(objective)
        if (
            not objective.strip()
            or len(objective) > 32000
            or bool(at) == bool(cron)
            or missed not in {"skip", "catch_up_once"}
            or overlap not in {"skip", "queue"}
        ):
            raise ValueError(
                "Edit needs a bounded objective, one future time or cron, timezone and explicit policies"
            )
        ZoneInfo(zone)
        current = aware(now or datetime.now(timezone.utc))
        fire = aware(at) if at else self._next(cron, zone, current)
        if fire <= current:
            raise ValueError("Edited occurrence must be in the future")
        with self.store.connect() as db:
            if (
                db.execute(
                    "UPDATE schedules SET objective=?,cron=?,zone=?,next=?,missed=?,overlap=? WHERE id=?",
                    (
                        objective,
                        cron,
                        zone,
                        fire.isoformat(),
                        missed,
                        overlap,
                        identity,
                    ),
                ).rowcount
                != 1
            ):
                raise StoreError("Unknown schedule")
        return self.get(identity)

    def get(self, identity):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM schedules WHERE id=?", (identity,)
            ).fetchone()
        if row is None:
            raise StoreError("Unknown schedule")
        return dict(
            zip(
                (
                    "id",
                    "agent",
                    "objective",
                    "cron",
                    "zone",
                    "next",
                    "missed",
                    "overlap",
                    "enabled",
                ),
                row,
            )
        )

    def list(self, name=None):
        with self.store.connect() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM schedules WHERE (? IS NULL OR agent=?)",
                    (name, name),
                )
            ]
        return [self.get(i) for i in ids]

    def action(self, identity, action):
        self.get(identity)
        with self.store.connect() as db:
            if action == "delete":
                db.execute("DELETE FROM schedules WHERE id=?", (identity,))
            elif action in {"pause", "resume"}:
                db.execute(
                    "UPDATE schedules SET enabled=? WHERE id=?",
                    (int(action == "resume"), identity),
                )
            else:
                raise StoreError("Unsupported schedule action")
        return {"id": identity, "action": action}

    def preview(self, identity, count=5):
        if not 1 <= count <= 20:
            raise ValueError("Preview count must be 1–20")
        schedule = self.get(identity)
        result = [schedule["next"]]
        while schedule["cron"] and len(result) < count:
            result.append(
                self._next(
                    schedule["cron"], schedule["zone"], aware(result[-1])
                ).isoformat()
            )
        return {
            "occurrences_utc": result,
            "zone": schedule["zone"],
            "dst": "Calendar trigger uses IANA timezone; offset distinguishes repeated wall-clock times",
            "runner_required": True,
        }

    def tick(self, *, now=None):
        current = aware(now or datetime.now(timezone.utc))
        created = []
        # A cross-process lock protects occurrence advancement and idempotent
        # submission as one recoverable protocol, without recursive SQLite locks.
        from filelock import FileLock

        with FileLock(str(self.store.root / "scheduler.lock"), timeout=0):
            for schedule in self.list():
                if self.store.get(schedule["agent"]).state != "active":
                    continue
                if not schedule["enabled"] or aware(schedule["next"]) > current:
                    continue
                active = [
                    j
                    for j in self.operations.list(schedule["agent"])
                    if j["status"] in {"queued", "running", "cancel_requested"}
                ]
                late = (current - aware(schedule["next"])).total_seconds() > 60
                if not (late and schedule["missed"] == "skip") and not (
                    active and schedule["overlap"] == "skip"
                ):
                    job = self.operations.submit(
                        schedule["agent"],
                        schedule["objective"],
                        idempotency=f"schedule:{schedule['id']}:{schedule['next']}",
                    )
                    created.append(job)
                with self.store.connect() as db:
                    if schedule["cron"]:
                        db.execute(
                            "UPDATE schedules SET next=? WHERE id=?",
                            (
                                self._next(
                                    schedule["cron"], schedule["zone"], current
                                ).isoformat(),
                                schedule["id"],
                            ),
                        )
                    else:
                        db.execute(
                            "UPDATE schedules SET enabled=0 WHERE id=?",
                            (schedule["id"],),
                        )
            self.operations.reconcile_stale()
        return created

    def run_once(self):
        """One runner cycle. Paused/retired agents cannot launch queued work."""
        self.tick()
        active_agents = {
            j["agent"]
            for j in self.operations.list()
            if j["status"] in {"running", "cancel_requested"}
        }
        for job in self.operations.list():
            if (
                job["status"] == "queued"
                and job["agent"] not in active_agents
                and self.store.get(job["agent"]).state == "active"
            ):
                try:
                    self.operations.launch(job["id"])
                except StoreError:
                    if (
                        self.store.get(job["agent"]).state != "active"
                        or self.operations.get(job["id"])["status"] != "queued"
                    ):
                        continue  # Pause/cancel won the race; do not kill the runner.
                    raise
                active_agents.add(job["agent"])

    def serve(self, stop=None, report=None):
        """Run until stopped; install with the user's OS service manager for boot."""
        from filelock import FileLock

        with FileLock(str(self.store.root / "runner.lock"), timeout=0):
            while stop is None or not stop.is_set():
                self.run_once()
                if report:
                    report()
                if stop is None:
                    time.sleep(2)
                else:
                    stop.wait(2)
