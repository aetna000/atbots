"""Portable private state and explicit Cloud Run Jobs deployment plans."""

import io
import json
import re
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path

from pydantic import Field, model_validator

from atbots.platform.jobs import Operations
from atbots.platform.models import AgentDefinition, Contract
from atbots.platform.store import AgentStore, StoreError


def export_definition(store, name):
    return {
        "format": "atbots-portable-v1",
        "definition": store.get(name).model_dump(mode="json"),
        "includes": "configuration only; no credentials, memory, history or browser session",
    }


def import_definition(store, manifest, *, allow_remote=False):
    if manifest.get("format") != "atbots-portable-v1" or set(manifest) - {
        "format",
        "definition",
        "includes",
    }:
        raise ValueError("Unsupported portable manifest")
    definition = AgentDefinition.model_validate(manifest["definition"])
    if definition.remote_allowed and not allow_remote:
        raise PermissionError(
            "Imported remote model requires a new explicit remote-access grant"
        )
    with store.connect() as db:
        try:
            db.execute(
                "INSERT INTO agents VALUES (?,?,?,?)",
                (
                    definition.id,
                    definition.name,
                    definition.revision,
                    definition.model_dump_json(),
                ),
            )
            db.execute(
                "INSERT INTO conversations VALUES (?,0,?)", (definition.id, b"[]")
            )
        except sqlite3.IntegrityError:
            raise StoreError(
                "Imported agent name/identity already exists; no overwrite"
            ) from None
    store.workspace(definition.name)
    return definition


def pack_state(store, name, key: bytes, *, activate_destination=False) -> bytes:
    """Explicitly authorized encrypted transfer; excludes browser/keychain state."""
    from cryptography.fernet import Fernet

    definition = store.get(name)
    if activate_destination and (
        definition.state != "paused"
        or any(
            j["status"] in {"queued", "paused", "running", "cancel_requested"}
            for j in Operations(store).list(name)
        )
    ):
        raise StoreError(
            "Cloud handoff requires a paused source and no unfinished local jobs; transfer schedules or submit destination work after reconciliation"
        )
    if any(
        j["status"] in {"running", "cancel_requested"}
        for j in Operations(store).list(name)
    ):
        raise StoreError("Quiesce running work before moving private agent state")
    with (
        store.turn_lock(name),
        tempfile.TemporaryDirectory(prefix="atbots-state-") as temporary,
    ):
        if any(
            j["status"] in {"running", "cancel_requested"}
            for j in Operations(store).list(name)
        ):
            raise StoreError(
                "Work started before snapshot lock; quiesce it before export"
            )
        clone = AgentStore(temporary)
        import_definition(clone, export_definition(store, name), allow_remote=True)
        if activate_destination:
            clone.configure(name, expected_revision=definition.revision, state="active")
        revision, history = store.history(name)
        with clone.connect() as db:
            db.execute(
                "UPDATE conversations SET revision=?,history=? WHERE agent_id=?",
                (revision, history, definition.id),
            )
            with store.connect() as source:
                for row in source.execute(
                    "SELECT id,agent_id,at,receipt FROM turns WHERE agent_id=?",
                    (definition.id,),
                ):
                    db.execute("INSERT INTO turns VALUES (?,?,?,?)", row)
                events_schema = source.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='job_events'"
                ).fetchone()
                if events_schema:
                    db.execute(
                        events_schema[0].replace(
                            "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1
                        )
                    )
                    for row in source.execute(
                        "SELECT e.* FROM job_events e JOIN jobs j ON e.job=j.id WHERE j.agent=?",
                        (name,),
                    ):
                        db.execute("INSERT INTO job_events VALUES (?,?,?,?,?)", row)
                # Jobs/schedules are private state, never active worker leases.
                for table in ("jobs", "schedules", "agent_supervision"):
                    schema = source.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (table,),
                    ).fetchone()
                    if schema:
                        db.execute(
                            schema[0].replace(
                                "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1
                            )
                        )
                        rows = source.execute(
                            f"SELECT * FROM {table} WHERE agent=?", (name,)
                        ).fetchall()
                        for row in rows:
                            db.execute(
                                f"INSERT INTO {table} VALUES ({','.join('?' for _ in row)})",
                                row,
                            )
        src, dst = store.workspace(name), clone.workspace(name)
        for path in src.rglob("*"):
            relative = path.relative_to(src)
            if set(relative.parts) & {"browser", "locks", "atsys-state"}:
                continue
            if path.is_symlink():
                raise StoreError("State export refuses symlinks")
            if not path.is_file() or path.name.endswith(("-wal", "-shm", "-journal")):
                continue
            if path.stat().st_size > 50_000_000:
                raise StoreError("State file exceeds 50 MB transfer limit")
            target = dst / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".db":
                source_db, target_db = sqlite3.connect(path), sqlite3.connect(target)
                try:
                    source_db.backup(target_db)
                finally:
                    source_db.close()
                    target_db.close()
            else:
                target.write_bytes(path.read_bytes())
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in Path(temporary).rglob("*"):
                if (
                    path.is_file()
                    and "browser" not in path.relative_to(temporary).parts
                    and "locks" not in path.relative_to(temporary).parts
                ):
                    archive.write(path, str(path.relative_to(temporary)))
        return Fernet(key).encrypt(output.getvalue())


def unpack_state(payload, root, key):
    from cryptography.fernet import Fernet

    root = Path(root).resolve()
    if root.exists() and any(root.iterdir()):
        raise StoreError("Restore destination must be empty; no overwrite")
    raw = Fernet(key).decrypt(payload)
    if len(raw) > 100_000_000:
        raise ValueError("State archive exceeds 100 MB")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 200_000_000:
            raise ValueError("Expanded archive exceeds transfer limit")
        for entry in archive.infolist():
            target = root / entry.filename
            if (
                not target.resolve().is_relative_to(root)
                or "browser" in Path(entry.filename).parts
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Unsafe state archive entry")
            if not entry.is_dir():
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                target.write_bytes(archive.read(entry))
                target.chmod(0o600)
    return AgentStore(root)


def stage_cloud_state(store, name, plan, key, *, client=None):
    """One-time handoff. Source stays paused; existing objects are never overwritten."""
    binding = store.get(name).binding
    if (
        binding.kind not in {"openai-compatible", "anthropic"}
        or binding.egress_class != "remote"
    ):
        raise StoreError(
            "Cloud model needs an explicit remote API binding; local Ollama and local subscription keychains cannot migrate"
        )
    if not binding.api_key_env or binding.api_key_env not in plan.model_secret_refs:
        raise StoreError(
            "Provision the configured API-key reference with cloud Secret Manager before transfer"
        )
    if client is None:
        from google.cloud import storage

        client = storage.Client(project=plan.project)
    with store.turn_lock(name), store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if store.get(name).state != "paused":
            raise StoreError("Pause the source before private-state handoff")
        db.execute(
            "INSERT INTO handoffs VALUES (?,?,?)",
            (
                name,
                "staging",
                json.dumps(
                    {"uri": plan.state_uri, "project": plan.project, "job": plan.job}
                ),
            ),
        )
    payload = pack_state(store, name, key, activate_destination=True)
    bucket, path = plan.state_uri[5:].split("/", 1)
    blob = client.bucket(bucket).blob(path)
    blob.upload_from_string(
        payload, if_generation_match=0, content_type="application/octet-stream"
    )
    blob.reload()
    with store.connect() as db:
        db.execute("UPDATE handoffs SET state='staged' WHERE agent=?", (name,))
    import hashlib

    return {
        "uri": plan.state_uri,
        "generation": str(blob.generation),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source_state": "paused",
        "browser_session_transferred": False,
        "warning": "Do not reactivate this local source while the remote state is authoritative",
    }


def build_container(wheel, image_tag, base_image, *, execute=subprocess.run):
    """Build/push only a wheel and the shipped recipe, never a project directory."""
    import hashlib
    import shutil
    from importlib.resources import files

    wheel = Path(wheel).resolve(strict=True)
    if (
        wheel.suffix != ".whl"
        or not re.fullmatch(r"[a-z0-9./:_-]+", image_tag)
        or not re.fullmatch(r"[a-z0-9./:_-]+@sha256:[a-f0-9]{64}", base_image)
    ):
        raise ValueError(
            "Build needs a wheel, explicit registry image tag and digest-pinned base"
        )
    with tempfile.TemporaryDirectory(prefix="atbots-image-") as directory:
        context = Path(directory)
        shutil.copyfile(wheel, context / wheel.name)
        (context / "Dockerfile").write_bytes(
            files("atbots.platform").joinpath("container.Dockerfile").read_bytes()
        )
        metadata = context / "image.json"
        execute(
            [
                "docker",
                "buildx",
                "build",
                "--push",
                "--provenance=true",
                "--platform=linux/amd64",
                "--tag",
                image_tag,
                "--metadata-file",
                str(metadata),
                "--build-arg",
                f"BASE_IMAGE={base_image}",
                "--build-arg",
                f"WHEEL_FILE={wheel.name}",
                str(context),
            ],
            check=True,
            timeout=1200,
            capture_output=True,
        )
        digest = json.loads(metadata.read_text())["containerimage.digest"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise RuntimeError(
                "Registry build did not return an immutable image digest"
            )
    return {
        "image": image_tag + "@" + digest,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "base_image": base_image,
    }


def restore_cloud_state(plan, key, destination, *, client=None):
    """Fence future cloud writers before restoring a new, paused local owner."""
    import uuid

    if Path(destination).exists() and any(Path(destination).iterdir()):
        raise StoreError("Cloud restore needs a new empty destination")
    if client is None:
        from google.cloud import storage

        client = storage.Client(project=plan.project)
    bucket_name, path = plan.state_uri[5:].split("/", 1)
    bucket = client.bucket(bucket_name)
    lease = bucket.blob(path + ".lease")
    owner = "local-handoff-" + uuid.uuid4().hex
    # A live/crashed remote owner prevents this create-only claim. Never steal
    # that lease or infer absence from a stale heartbeat.
    lease.upload_from_string(
        json.dumps({"owner": owner, "handoff": True}), if_generation_match=0
    )
    state = bucket.blob(path)
    state.reload()
    restored = unpack_state(
        state.download_as_bytes(if_generation_match=state.generation), destination, key
    )
    definitions = restored.list()
    if len(definitions) != 1:
        raise StoreError("Cloud restore must contain one agent")
    definition = definitions[0]
    paused = restored.configure(
        definition.name, expected_revision=definition.revision, state="paused"
    )
    return {
        "root": str(restored.root),
        "agent": paused.name,
        "state": "paused",
        "cloud_fence": owner,
        "source_generation": str(state.generation),
        "next": "Provision local model credentials, run doctor, then explicitly activate this new local store. Remote lease remains fenced.",
    }


class CloudPlan(Contract):
    project: str = Field(pattern=r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
    region: str = Field(pattern=r"^[a-z]+-[a-z]+[0-9]$")
    job: str = Field(pattern=r"^[a-z][a-z0-9-]{0,40}$")
    image: str = Field(pattern=r"^[a-z0-9./:_-]+@sha256:[a-f0-9]{64}$")
    state_uri: str = Field(pattern=r"^gs://[a-z0-9.-]+/[a-zA-Z0-9/_-]+$")
    service_account: str = Field(
        pattern=r"^[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com$"
    )
    state_key_secret: str = Field(pattern=r"^[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+$")
    model_secret_refs: dict[str, str] = Field(default_factory=dict, max_length=8)
    timeout_seconds: int = Field(default=300, ge=30, le=3600)
    max_executions: int = Field(default=1, ge=1, le=100)
    cron: str | None = None
    timezone: str = "UTC"
    spending_grant_usd: float = Field(gt=0, le=100)
    state_transfer_authorized: bool = False
    acknowledges_not_hard_billing_cap: bool = False

    @model_validator(mode="after")
    def explicit_grants(self):
        if self.cron:
            from zoneinfo import ZoneInfo

            from apscheduler.triggers.cron import CronTrigger

            CronTrigger.from_crontab(self.cron, timezone=ZoneInfo(self.timezone))
        if (
            not self.state_transfer_authorized
            or not self.acknowledges_not_hard_billing_cap
        ):
            raise ValueError(
                "Deployment needs explicit private-state transfer and non-hard-cap spending acknowledgement"
            )
        for name, reference in self.model_secret_refs.items():
            if (
                not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", name)
                or not re.fullmatch(r"[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+", reference)
                or name.startswith("ATBOTS_")
                or name
                in {
                    "HOME",
                    "PATH",
                    "PYTHONHOME",
                    "PYTHONPATH",
                    "LD_PRELOAD",
                    "LD_LIBRARY_PATH",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                }
            ):
                raise ValueError("Invalid cloud model-secret reference")
        return self


class CloudRun:
    def __init__(self, execute=subprocess.run):
        self.execute = execute

    def command(self, plan, action):
        if action in {"schedule", "unschedule"}:
            prefix = ["gcloud", "scheduler", "jobs"]
            common = [
                "--project",
                plan.project,
                "--location",
                plan.region,
                "--quiet",
                "--format=json",
            ]
            if action == "unschedule":
                return prefix + ["delete", plan.job + "-trigger", *common]
            if not plan.cron:
                raise ValueError(
                    "Cloud trigger needs an explicitly approved cron and timezone"
                )
            return prefix + [
                "create",
                "http",
                plan.job + "-trigger",
                *common,
                "--schedule",
                plan.cron,
                "--time-zone",
                plan.timezone,
                "--uri",
                f"https://run.googleapis.com/v2/projects/{plan.project}/locations/{plan.region}/jobs/{plan.job}:run",
                "--http-method=POST",
                "--oauth-service-account-email",
                plan.service_account,
                "--message-body={}",
                "--max-retry-attempts=0",
            ]
        common = [
            "--project",
            plan.project,
            "--region",
            plan.region,
            "--format=json",
            "--quiet",
        ]
        base = ["gcloud", "run", "jobs"]
        if action == "deploy":
            return base + [
                "deploy",
                plan.job,
                *common,
                "--image",
                plan.image,
                "--service-account",
                plan.service_account,
                "--tasks=1",
                "--parallelism=1",
                "--max-retries=0",
                "--cpu=1",
                "--memory=2Gi",
                f"--task-timeout={plan.timeout_seconds}s",
                "--command=python",
                "--args=-m,atbots.platform.cloud_worker",
                "--set-env-vars",
                f"ATBOTS_STATE_URI={plan.state_uri},ATBOTS_MAX_EXECUTIONS={plan.max_executions}",
                "--set-secrets",
                ",".join(
                    [f"ATBOTS_STATE_KEY={plan.state_key_secret}"]
                    + [
                        f"{name}={reference}"
                        for name, reference in plan.model_secret_refs.items()
                    ]
                ),
            ]
        if action == "status":
            return base + ["describe", plan.job, *common]
        if action == "run":
            return base + ["execute", plan.job, *common]
        if action == "destroy":
            return base + ["delete", plan.job, *common]
        if action == "logs":
            return [
                "gcloud",
                "logging",
                "read",
                f'resource.type="cloud_run_job" AND resource.labels.job_name="{plan.job}"',
                "--project",
                plan.project,
                "--format=json",
                "--limit=50",
            ]
        raise ValueError(
            "Unsupported deployment action; stop requires the exact execution ID"
        )

    def apply(self, plan, action):
        try:
            result = self.execute(
                self.command(plan, action),
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            return json.loads(result.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError):
            raise RuntimeError(
                "Cloud operation failed; inspect project/IAM/image/state and reconcile any uncertain resource change. No automatic retry was performed"
            ) from None

    def stop(self, plan, execution):
        if not isinstance(execution, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{0,62}", execution
        ):
            raise ValueError("Invalid execution ID")
        return self.execute(
            [
                "gcloud",
                "run",
                "jobs",
                "executions",
                "cancel",
                execution,
                "--project",
                plan.project,
                "--region",
                plan.region,
                "--quiet",
            ],
            check=True,
            timeout=60,
            capture_output=True,
        )
