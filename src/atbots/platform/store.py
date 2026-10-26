"""Private local definitions and native conversation history, not memory truth."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock, Timeout

from atbots.platform.models import AgentDefinition, ModelBinding, RunLimits, agent_name


class StoreError(RuntimeError):
    pass


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.root / "agents.sqlite"
        if self.database.is_symlink():
            raise StoreError("Registry must not be a symlink")
        with self.connect() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise StoreError(
                    "Registry schema is newer than this AtBots version; upgrade before opening"
                )
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                  id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                  revision INTEGER NOT NULL, definition TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS conversations (
                  agent_id TEXT PRIMARY KEY REFERENCES agents(id),
                  revision INTEGER NOT NULL DEFAULT 0, history BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS turns (
                  id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id),
                  at TEXT NOT NULL, receipt TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_shares (
                  source_id TEXT NOT NULL REFERENCES agents(id),
                  recipient_id TEXT NOT NULL REFERENCES agents(id),
                  at TEXT NOT NULL, PRIMARY KEY(source_id,recipient_id));
                PRAGMA user_version=1;
                CREATE TABLE IF NOT EXISTS handoffs (
                  agent TEXT PRIMARY KEY,state TEXT NOT NULL,receipt TEXT NOT NULL);
            """)
        if os.name != "nt":
            self.database.chmod(0o600)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(
        self,
        name: str,
        *,
        binding: ModelBinding | None = None,
        remote_allowed: bool = False,
        instructions: str | None = None,
        limits: RunLimits | None = None,
    ) -> AgentDefinition:
        agent_name(name)
        values = {
            "id": uuid.uuid4().hex,
            "name": name,
            "created_at": stamp(),
            "binding": binding or ModelBinding(),
            "remote_allowed": remote_allowed,
            "limits": limits or RunLimits(),
        }
        if instructions is not None:
            values["instructions"] = instructions
        definition = AgentDefinition(**values)
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO agents VALUES (?,?,?,?)",
                    (definition.id, name, 1, definition.model_dump_json()),
                )
                db.execute(
                    "INSERT INTO conversations VALUES (?,0,?)", (definition.id, b"[]")
                )
        except sqlite3.IntegrityError:
            raise StoreError(
                "Agent already exists; reopen it or choose another name"
            ) from None
        self.workspace(name)
        return definition

    def get(self, name: str) -> AgentDefinition:
        agent_name(name)
        with self.connect() as db:
            row = db.execute(
                "SELECT definition FROM agents WHERE name=?", (name,)
            ).fetchone()
        if row is None:
            raise StoreError(f"Agent {name!r} does not exist; create it first")
        return AgentDefinition.model_validate_json(row[0])

    def list(self) -> list[AgentDefinition]:
        with self.connect() as db:
            return [
                AgentDefinition.model_validate_json(r[0])
                for r in db.execute("SELECT definition FROM agents ORDER BY name")
            ]

    def workspace(self, name: str) -> Path:
        definition = self.get(name)
        directory = self.root / "workspaces" / definition.id
        if directory.resolve() != directory:
            raise StoreError("Agent workspace must not traverse a symlink")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for child in ("files", "browser", "locks"):
            path = directory / child
            if path.is_symlink():
                raise StoreError("Agent directories must not be symlinks")
            path.mkdir(exist_ok=True, mode=0o700)
        return directory

    @contextmanager
    def turn_lock(self, name: str) -> Iterator[None]:
        path = self.workspace(name) / "locks" / "turn.lock"
        try:
            with FileLock(str(path), timeout=0, mode=0o600):
                yield
        except Timeout:
            raise StoreError(
                "Agent is busy; this operation did not interrupt its work"
            ) from None

    def configure(
        self, name: str, *, expected_revision: int, **changes: object
    ) -> AgentDefinition:
        if not changes or set(changes) - {
            "binding",
            "limits",
            "remote_allowed",
            "instructions",
            "state",
            "capabilities",
        }:
            raise StoreError("Unsupported or empty configuration change")
        with self.turn_lock(name):
            with self.connect() as db:
                if db.execute(
                    "SELECT 1 FROM handoffs WHERE agent=?", (name,)
                ).fetchone():
                    raise StoreError(
                        "Agent has a fenced handoff; reconcile the remote execution owner before local changes"
                    )
            old = self.get(name)
            data = old.model_dump()
            data.update(changes, revision=old.revision + 1)
            new = AgentDefinition.model_validate(data)
            with self.connect() as db:
                changed = db.execute(
                    "UPDATE agents SET definition=?,revision=? WHERE id=? AND revision=?",
                    (new.model_dump_json(), new.revision, new.id, expected_revision),
                ).rowcount
                if changed != 1:
                    raise StoreError(
                        "Configuration changed; inspect and retry using its current revision"
                    )
            return new

    def history(self, name: str) -> tuple[int, bytes]:
        identity = self.get(name).id
        with self.connect() as db:
            row = db.execute(
                "SELECT revision,history FROM conversations WHERE agent_id=?",
                (identity,),
            ).fetchone()
        if row is None:
            raise StoreError("Missing conversation; registry needs recovery")
        return row[0], bytes(row[1])

    def save_turn(
        self, name: str, expected_revision: int, history: bytes, receipt: dict
    ) -> None:
        if len(history) > 8_000_000:
            raise StoreError(
                "Conversation exceeds local history limit; export before starting another session"
            )
        identity = self.get(name).id
        with self.connect() as db:
            changed = db.execute(
                "UPDATE conversations SET revision=revision+1,history=? WHERE agent_id=? AND revision=?",
                (history, identity, expected_revision),
            ).rowcount
            if changed != 1:
                raise StoreError(
                    "Conversation changed; refusing to overwrite another turn"
                )
            db.execute(
                "INSERT INTO turns VALUES (?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    identity,
                    stamp(),
                    json.dumps(receipt, allow_nan=False),
                ),
            )

    def receipts(self, name: str) -> list[dict]:
        identity = self.get(name).id
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT receipt FROM turns WHERE agent_id=? ORDER BY rowid",
                    (identity,),
                )
            ]

    def record_failure(self, name: str, receipt: dict) -> None:
        identity = self.get(name).id
        with self.connect() as db:
            db.execute(
                "INSERT INTO turns VALUES (?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    identity,
                    stamp(),
                    json.dumps(receipt, allow_nan=False),
                ),
            )

    def share_memory(self, source: str, recipient: str, *, enabled: bool) -> dict:
        a, b = self.get(source), self.get(recipient)
        if a.id == b.id:
            raise StoreError("Memory sharing requires two different agents")
        with self.connect() as db:
            if enabled:
                db.execute(
                    "INSERT OR REPLACE INTO memory_shares VALUES (?,?,?)",
                    (a.id, b.id, stamp()),
                )
            else:
                db.execute(
                    "DELETE FROM memory_shares WHERE source_id=? AND recipient_id=?",
                    (a.id, b.id),
                )
        return {
            "source": source,
            "recipient": recipient,
            "enabled": enabled,
            "operations": ["recall"],
            "revocation": "future access only; previous exposure cannot be undone",
        }

    def shared_sources(self, recipient: str) -> list[str]:
        identity = self.get(recipient).id
        with self.connect() as db:
            return [
                r[0]
                for r in db.execute(
                    "SELECT a.name FROM agents a JOIN memory_shares s ON a.id=s.source_id WHERE s.recipient_id=? AND json_extract(a.definition,'$.state')!='retired'",
                    (identity,),
                )
            ]
