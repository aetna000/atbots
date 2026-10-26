"""Durable bounded job lifecycle and approval receipts; no model loop."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid

from atbots.platform.memory import screen_message
from atbots.platform.store import AgentStore, StoreError, stamp


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Operations:
    def __init__(self, store: AgentStore):
        self.store = store
        with store.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,payload TEXT NOT NULL,
                digest TEXT NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL,result TEXT);
              CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,agent TEXT NOT NULL,
                definition_revision INTEGER NOT NULL,objective TEXT NOT NULL,owner TEXT NOT NULL,
                status TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL,
                token TEXT,lease REAL,pid INTEGER,result TEXT,idempotency TEXT UNIQUE);
              CREATE TABLE IF NOT EXISTS job_events(id INTEGER PRIMARY KEY AUTOINCREMENT,
                job TEXT NOT NULL,at TEXT NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL);
            """)

    def propose(self, payload: dict, *, now=None, ttl=300) -> str:
        raw = canonical(payload)
        screen_message(raw)
        identity = uuid.uuid4().hex
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO approvals VALUES (?,?,?,?,?,NULL)",
                (
                    identity,
                    raw,
                    digest,
                    (time.time() if now is None else now) + ttl,
                    "pending",
                ),
            )
        return identity

    def consume(self, identity: str, *, now=None, preview=False) -> dict:
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload,digest,expires,state FROM approvals WHERE id=?",
                (identity,),
            ).fetchone()
            if (
                row is None
                or row[3] != "pending"
                or row[2] < (time.time() if now is None else now)
            ):
                raise StoreError("Approval is missing, expired or already used")
            if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
                raise StoreError("Approval payload integrity failure")
            if not preview:
                db.execute(
                    "UPDATE approvals SET state='executing' WHERE id=?", (identity,)
                )
        return json.loads(row[0])

    def finish_approval(self, identity, result):
        with self.store.connect() as db:
            db.execute(
                "UPDATE approvals SET state='applied',result=? WHERE id=? AND state='executing'",
                (canonical(result), identity),
            )

    def reject(self, identity):
        with self.store.connect() as db:
            db.execute(
                "UPDATE approvals SET state='rejected' WHERE id=? AND state='pending'",
                (identity,),
            )

    def submit(
        self, name: str, objective: str, *, idempotency: str | None = None
    ) -> dict:
        if not objective.strip() or len(objective) > 32000:
            raise ValueError("Job objective must contain 1–32000 characters")
        screen_message(objective)
        definition = self.store.get(name)
        if definition.state != "active":
            raise StoreError("Agent must be active before submitting work")
        key = idempotency or uuid.uuid4().hex
        identity, at = uuid.uuid4().hex, stamp()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT id,agent,objective FROM jobs WHERE idempotency=?", (key,)
            ).fetchone()
            if old:
                if old[1:] != (name, objective):
                    raise StoreError("Idempotency key reused for a different objective")
                identity = old[0]
            else:
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,?)",
                    (
                        identity,
                        name,
                        definition.revision,
                        objective,
                        "atbot",
                        "queued",
                        at,
                        at,
                        key,
                    ),
                )
                db.execute(
                    "INSERT INTO job_events(job,at,kind,detail) VALUES (?,?,?,?)",
                    (identity, at, "queued", "Objective accepted; not yet executed"),
                )
        return self.get(identity)

    def get(self, identity: str) -> dict:
        with self.store.connect() as db:
            db.row_factory = __import__("sqlite3").Row
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise StoreError("Unknown job ID")
            result = dict(row)
            result.pop("token", None)
            if result["result"]:
                result["result"] = json.loads(result["result"])
            result["events"] = [
                dict(r)
                for r in db.execute(
                    "SELECT at,kind,detail FROM job_events WHERE job=? ORDER BY id",
                    (identity,),
                )
            ]
        result["stale"] = (
            result["status"] in {"running", "cancel_requested"}
            and (result["lease"] or 0) < time.time()
        )
        return result

    def list(self, name=None):
        with self.store.connect() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM jobs WHERE (? IS NULL OR agent=?) ORDER BY created",
                    (name, name),
                )
            ]
        return [self.get(i) for i in ids]

    def claim(self, identity: str) -> str:
        token = uuid.uuid4().hex
        with (
            self.store.turn_lock(self.get(identity)["agent"]),
            self.store.connect() as db,
        ):
            db.execute("BEGIN IMMEDIATE")
            job = db.execute(
                "SELECT agent FROM jobs WHERE id=?", (identity,)
            ).fetchone()
            if job is None:
                raise StoreError("Unknown job ID")
            if self.store.get(job[0]).state != "active":
                raise StoreError("Agent is paused or retired; work remains queued")
            if db.execute(
                "SELECT 1 FROM jobs WHERE agent=? AND status IN ('running','cancel_requested')",
                (job[0],),
            ).fetchone():
                raise StoreError(
                    "Agent already owns active work; this job remains queued"
                )
            changed = db.execute(
                "UPDATE jobs SET status='running',token=?,lease=?,pid=?,updated=? WHERE id=? AND status='queued'",
                (token, time.time() + 30, os.getpid(), stamp(), identity),
            ).rowcount
            if changed != 1:
                raise StoreError(
                    "Job already claimed or not queued; no replay was started"
                )
        return token

    def pending_approvals(self):
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT id,payload,expires,state,result FROM approvals WHERE state IN ('pending','executing') ORDER BY expires"
            ).fetchall()
        return [
            {
                "id": row[0],
                "proposal": json.loads(row[1])["plan"],
                "expires": row[2],
                "state": row[3],
                "expired": row[2] < time.time(),
                "result": json.loads(row[4]) if row[4] else None,
            }
            for row in rows
        ]

    def heartbeat(self, identity: str, token: str) -> str:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT status FROM jobs WHERE id=? AND token=?", (identity, token)
            ).fetchone()
            if row is None:
                raise StoreError("Worker lease was fenced")
            if row[0] in {"running", "cancel_requested"}:
                db.execute(
                    "UPDATE jobs SET lease=?,updated=? WHERE id=? AND token=?",
                    (time.time() + 30, stamp(), identity, token),
                )
        return row[0]

    def finish(self, identity, token, status, result):
        if status not in {"replied", "failed", "needs_review", "cancelled"}:
            raise StoreError("Invalid terminal status")
        screen_message(canonical(result))
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT status FROM jobs WHERE id=? AND token=?", (identity, token)
            ).fetchone()
            if current and current[0] == "cancel_requested":
                status = "needs_review"
            changed = db.execute(
                "UPDATE jobs SET status=?,result=?,lease=NULL,updated=? WHERE id=? AND token=? AND status IN ('running','cancel_requested')",
                (status, canonical(result), stamp(), identity, token),
            ).rowcount
            if changed != 1:
                raise StoreError(
                    "Worker result was fenced; no terminal state was overwritten"
                )
            db.execute(
                "INSERT INTO job_events(job,at,kind,detail) VALUES (?,?,?,?)",
                (
                    identity,
                    stamp(),
                    status,
                    "See persisted result; objective acceptance is separate",
                ),
            )

    def action(self, identity: str, action: str) -> dict:
        with self.store.connect() as db:
            if action == "cancel":
                db.execute(
                    "UPDATE jobs SET status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancel_requested' END,updated=? WHERE id=? AND status IN ('queued','running')",
                    (stamp(), identity),
                )
            elif action == "pause":
                if (
                    db.execute(
                        "UPDATE jobs SET status='paused',updated=? WHERE id=? AND status='queued'",
                        (stamp(), identity),
                    ).rowcount
                    != 1
                ):
                    raise StoreError(
                        "Only queued local jobs can pause safely; cancel an active job or use AtSys process control"
                    )
            elif action == "resume":
                if (
                    db.execute(
                        "UPDATE jobs SET status='queued',updated=? WHERE id=? AND status='paused'",
                        (stamp(), identity),
                    ).rowcount
                    != 1
                ):
                    raise StoreError("Only paused local jobs can resume")
            else:
                raise StoreError("Unsupported job action")
        return self.get(identity)

    def reconcile_stale(self):
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT id FROM jobs WHERE status IN ('running','cancel_requested') AND lease<?",
                (time.time(),),
            ).fetchall()
            for (identity,) in rows:
                db.execute(
                    "UPDATE jobs SET status='needs_review',token=NULL,updated=?,result=? WHERE id=?",
                    (
                        stamp(),
                        canonical(
                            {
                                "reason": "Worker heartbeat expired; reconcile external effects before retry",
                                "verified": False,
                            }
                        ),
                        identity,
                    ),
                )
        return len(rows)

    def launch(self, identity):
        job = self.get(identity)
        if job["status"] != "queued":
            raise StoreError("Only queued work can launch")
        if self.store.get(job["agent"]).state != "active":
            raise StoreError("Agent is paused or retired; work remains queued")
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "atbots.platform.worker",
                "--root",
                str(self.store.root),
                "--job",
                identity,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
        )
        return self.get(identity)

    def amend(self, identity: str, objective: str):
        screen_message(objective)
        if not objective.strip() or len(objective) > 32000:
            raise ValueError("Invalid objective")
        with self.store.connect() as db:
            if (
                db.execute(
                    "UPDATE jobs SET objective=?,updated=? WHERE id=? AND status IN ('queued','paused')",
                    (objective, stamp(), identity),
                ).rowcount
                != 1
            ):
                raise StoreError(
                    "Running work cannot be silently amended; cancel/reconcile or use supported execution-owner controls"
                )
        return self.get(identity)
