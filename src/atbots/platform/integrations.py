"""Explicit adapters to existing AtSys and AtFlows contracts."""

import json
from importlib import metadata, resources
from typing import Literal
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import Field, model_validator

from atbots.platform.memory import screen_message
from atbots.platform.models import Contract, ModelBinding
from atbots.platform.store import StoreError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise PermissionError("Integration redirects are refused")


def loopback_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Local integration requires a credential-free loopback HTTP URL"
        )
    return url.rstrip("/")


class SupervisedObjective(Contract):
    endpoint: str = "http://127.0.0.1:4310"
    worker: str = "codex"
    model: str = ""
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium"
    supervisor_provider: str = "codex"
    supervisor_model: str = ""
    supervisor_effort: Literal["low", "medium", "high", "xhigh"] = "medium"
    repair_provider: str = "codex"
    repair_model: str = ""
    repair_effort: Literal["low", "medium", "high", "xhigh"] = "medium"
    trusted_local_execution: bool = False
    allow_repair: bool = False
    network_access: bool = False
    validation_argv: list[str] = Field(min_length=1, max_length=50)
    required_artifacts: list[str] = Field(default_factory=list, max_length=20)
    success_criteria: list[str] = Field(min_length=1, max_length=20)
    stages: list[str] = Field(min_length=1, max_length=20)
    plan: str = Field(min_length=1, max_length=12000)

    @model_validator(mode="after")
    def permissions(self):
        loopback_url(self.endpoint)
        for provider in (self.worker, self.supervisor_provider, self.repair_provider):
            if provider not in {"codex", "claude", "copilot"}:
                raise ValueError("Supported AtSys providers: codex, claude, copilot")
        if (
            self.worker != "codex"
            or self.allow_repair
            and self.repair_provider != "codex"
        ) and not self.trusted_local_execution:
            raise ValueError(
                "Claude/Copilot tools require explicit trusted local execution"
            )
        return self


class AtSysClient:
    def __init__(self, endpoint):
        self.endpoint = loopback_url(endpoint)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, *, method="GET", data=None):
        raw = None if data is None else json.dumps(data).encode()
        if raw is not None:
            screen_message(raw.decode())
        request = Request(
            self.endpoint + path,
            data=raw,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise RuntimeError("AtSys response exceeds the bounded adapter limit")
            return json.loads(body)
        except (OSError, ValueError, RuntimeError):
            raise RuntimeError(
                "AtSys request failed; check service/version/permissions. A failed mutation may have an uncertain outcome; no automatic retry was made"
            ) from None

    def health(self):
        from packaging.version import Version

        health = self.request("/api/health")
        if Version(health.get("version", "0")) < Version("0.3.0b4"):
            raise RuntimeError(
                "AtSys >=0.3.0b4 is required for multi-provider supervision; the running service is older"
            )
        return health

    def submit(self, definition, workspace, objective, contract: SupervisedObjective):
        if not 3 <= len(objective) <= 6000:
            raise ValueError("AtSys objective must contain 3–6000 characters")
        self.readiness()
        try:
            from packaging.version import Version

            if Version(metadata.version("atsys")) < Version("0.3.0b4"):
                raise RuntimeError(
                    "Installed AtSys resource schema is older than 0.3.0b4"
                )
            defaults = json.loads(
                (
                    resources.files("atsys") / "resources" / "task-defaults.json"
                ).read_text()
            )
        except metadata.PackageNotFoundError:
            raise RuntimeError(
                'Install the optional adapter: python -m pip install "atbots[supervision]"'
            ) from None
        defaults.update(
            name=f"AtBot {definition.name}",
            objective=objective,
            cwd=str(workspace),
            worker=contract.worker,
            model=contract.model,
            reasoningEffort=contract.reasoning_effort,
            supervisorProvider=contract.supervisor_provider,
            supervisorModel=contract.supervisor_model,
            supervisorEffort=contract.supervisor_effort,
            repairProvider=contract.repair_provider,
            repairModel=contract.repair_model,
            repairEffort=contract.repair_effort,
            trustedLocalExecution=contract.trusted_local_execution,
            allowRepair=contract.allow_repair,
            networkAccess=contract.network_access,
            validator="command",
            validationArgv=contract.validation_argv,
            requiredArtifacts=contract.required_artifacts,
            plan=contract.plan,
            timeoutSeconds=definition.limits.timeout_seconds,
            taskTimeoutSeconds=definition.limits.timeout_seconds * 3,
            maxRetries=1,
            maxSupervisorCalls=1,
        )
        defaults["goalContract"] = {
            "version": 1,
            "successCriteria": contract.success_criteria,
            "deliverables": contract.required_artifacts or ["Verified task result"],
            "constraints": [
                "Keep changes in the approved agent workspace",
                "Do not recursively submit AtSys tasks",
            ],
            "assumptions": [],
            "unresolvedDecisions": [],
            "stages": contract.stages,
            "planSource": "AtBots operator-approved supervised objective",
            "observers": [
                {
                    "signal": "validator",
                    "cadenceSeconds": 30,
                    "rationale": "Independent acceptance of bounded local objective",
                }
            ],
            "recoveryScope": "One bounded retry within the same objective and permissions",
            "escalationConditions": [
                "Uncertain external effect",
                "Missing permission",
                "Budget/deadline exhausted",
            ],
            "budget": f"Attempt timeout {definition.limits.timeout_seconds}s; one retry and supervisor call; monetary cost unknown",
        }
        return self.request("/api/tasks", method="POST", data=defaults)

    def readiness(self):
        health = self.health()
        state = self.request("/api/operations")
        daemon = state.get("daemon")
        if daemon and (
            daemon.get("providerProtocol") != 1 or not state.get("daemonHealthy", False)
        ):
            raise StoreError(
                "AtSys dashboard is reachable but its watchdog is old or unhealthy. Open this agent's Supervision and choose Start private AtSys; existing shared work will not be restarted"
            )
        return health

    def status(self, identity):
        tasks = self.request("/api/operations")["tasks"]
        for task in tasks:
            if task["id"] == identity:
                return task
        raise ValueError("AtSys task is not present in this service")

    def action(self, identity, action):
        if (
            action not in {"stop", "pause", "resume"}
            or not identity.startswith("task-")
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in identity)
        ):
            raise ValueError("Unsupported AtSys task action or ID")
        return self.request(f"/api/tasks/{identity}/{action}", method="POST", data={})

    def report(self, identity):
        if not identity.startswith("task-") or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in identity
        ):
            raise ValueError("Invalid AtSys task ID")
        return self.request(f"/api/tasks/{identity}/report")

    def amend(self, identity, changes):
        task = self.status(identity)
        if task.get("status") not in {"queued", "paused", "needs_attention", "stopped"}:
            raise ValueError(
                "Amendment needs a non-running task; pause through AtSys first"
            )
        if set(changes) - {"objective", "plan"}:
            raise ValueError(
                "Amendments cannot broaden permissions or change execution owner"
            )
        config = {**task["config"], **changes}
        return self.request(
            f"/api/tasks/{identity}",
            method="PATCH",
            data={"config": config, "revision": task["revision"]},
        )


class Delegations:
    """Only upstream AtSys owns execution; this registry stores correlation."""

    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS delegations(id TEXT PRIMARY KEY,agent TEXT NOT NULL,endpoint TEXT NOT NULL,upstream_id TEXT NOT NULL,receipt TEXT NOT NULL)"
            )

    def record(self, name, endpoint, result):
        import uuid

        task = result.get("task", result)
        identity = task.get("id")
        if not isinstance(identity, str) or not identity.startswith("task-"):
            raise RuntimeError(
                "AtSys did not return a task identity; reconcile upstream before resubmitting"
            )
        key = uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO delegations VALUES (?,?,?,?,?)",
                (key, name, loopback_url(endpoint), identity, json.dumps(result)),
            )
        return self.get(key)

    def get(self, identity):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT id,agent,endpoint,upstream_id FROM delegations WHERE id=?",
                (identity,),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown delegated objective")
        return dict(zip(("id", "agent", "endpoint", "upstream_id"), row))

    def list(self):
        with self.store.connect() as db:
            ids = [
                r[0] for r in db.execute("SELECT id FROM delegations ORDER BY rowid")
            ]
        return [self.get(i) for i in ids]

    def observe(self, identity):
        link = self.get(identity)
        return {
            **link,
            "execution_owner": "atsys",
            "state": AtSysClient(link["endpoint"]).status(link["upstream_id"]),
        }

    def action(self, identity, action):
        link = self.get(identity)
        return AtSysClient(link["endpoint"]).action(link["upstream_id"], action)


def atflows_binding(binding: ModelBinding, endpoint: str) -> ModelBinding:
    if binding.kind not in {"ollama", "openai-compatible"}:
        raise ValueError(
            "Subscription/native providers cannot be silently redirected through a compatible proxy"
        )
    loopback_url(endpoint)
    return ModelBinding.model_validate(
        {**binding.model_dump(), "kind": "openai-compatible", "endpoint": endpoint}
    )
