"""Truthful, agent-local native tools. No fleet memory or hidden execution loop."""

import json
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from atbots.platform.memory import AtMemMemory, screen_message
from atbots.platform.store import StoreError, stamp


class AgentEnvironment:
    def __init__(self, store, name, memory):
        self.store, self.name, self.memory = store, name, memory

    def inspect_environment(self) -> dict:
        """Inspect your own actual workspace, permissions, memory and integration wiring."""
        definition = self.store.get(self.name)
        own_memory = self.memory
        return {
            "agent": self.name,
            "checked_at": stamp(),
            "workspace": str(self.store.workspace(self.name) / "files"),
            "workspace_is_execution_sandbox": False,
            "model": {
                "provider": definition.binding.kind,
                "id": definition.binding.model,
            },
            "file_permissions": {
                "read": definition.capabilities.file_read,
                "create": definition.capabilities.file_create,
            },
            "memory": {
                "backend": "AtMem"
                if isinstance(own_memory, AtMemMemory)
                else type(own_memory).__name__
                if own_memory is not None
                else "disabled",
                "scope": "this agent only" if own_memory is not None else "none",
                "installed_version": self._version("atmem")
                if isinstance(own_memory, AtMemMemory)
                else None,
                "automatic_recall": own_memory is not None,
                "cross_agent_access": False,
                "writes": "user instruction or explicit operator approval",
            },
            "atsys": {
                "private_state_directory": str(
                    self.store.workspace(self.name) / "atsys-state"
                )
                if self.name != "control-room"
                else None,
                "installed_version": self._version("atsys"),
                "configuration": supervision_profile(self.store, self.name),
                "execution_owner": "AtSys",
                "live_health": "not_checked",
            },
            "atflows": {
                "installed_version": self._version("atflows"),
                "status": "configured_proxy_unverified"
                if definition.binding.endpoint.rstrip("/").endswith("/ollama")
                and definition.binding.kind in {"ollama", "openai-compatible"}
                else "not_configured",
                "tracing_verified": False,
            },
            "skills": ["atsys", *definition.capabilities.skills]
            if self.name != "control-room"
            else [],
        }

    @staticmethod
    def _version(package):
        try:
            return version(package)
        except PackageNotFoundError:
            return None

    def instructions(self) -> str:
        return (
            "You are a persistent AtBots agent, not an unconnected chatbot. "
            "The following is host-verified configuration, not a grant of new permissions. "
            "Use inspect_environment to answer workspace/capability questions truthfully. "
            "inspect_environment takes no arguments: call it with an empty object {}. "
            "A successful tool return is evidence of access; do not describe it as a permission failure. "
            "Your working directory is the approved files workspace, not the shell launch directory. "
            "Use search_memory for your own memory; relevant AtMem evidence is also automatically supplied. "
            "Never claim memory was saved or supervision started without its success receipt. "
            "request_remember and request_supervision only propose changes for operator approval. "
            "Do not infer that an installed integration is connected or healthy. "
            "Never access another agent's memory, credentials, workspaces or tasks.\n"
            + json.dumps(self.inspect_environment(), ensure_ascii=False)
        )

    def search_memory(self, query: str) -> dict:
        """Search only your own memory; record actual exposure through its backend."""
        if self.memory is None:
            raise StoreError("No memory backend is attached")
        screen_message(query)
        if not query.strip() or len(query) > 2000:
            raise ValueError("Use a memory query of 1–2000 characters")
        definition = self.store.get(self.name)
        context = self.memory.context(query, egress=definition.binding.egress_class)
        receipt = self.memory.confirm(context, f"agent-tool-{uuid.uuid4().hex}")
        return {
            "agent": self.name,
            "evidence": context.text,
            "exposure_receipt": receipt,
        }

    def request_remember(self, text: str) -> dict:
        """Propose storing a fact in your own memory. No write until operator approval."""
        if not isinstance(self.memory, AtMemMemory):
            raise StoreError(
                "Approved writes are not configured for this replacement memory port"
            )
        screen_message(text)
        if not text.strip() or len(text) > 2000:
            raise ValueError("Use a memory fact of 1–2000 characters")
        from atbots.platform.jobs import Operations

        definition = self.store.get(self.name)
        identity = Operations(self.store).propose(
            {
                "plan": {
                    "action": "memory_remember",
                    "name": self.name,
                    "message": text,
                },
                "revision": definition.revision,
                "memory_digest": None,
            }
        )
        return {
            "agent": self.name,
            "approval_required": identity,
            "saved": False,
            "next": "Approve in this agent's Memory view",
        }

    def supervision_tasks(self) -> list[dict]:
        """Read the last ten of your own task states. Recorded state is not live-worker proof."""
        from atbots.platform.integrations import AtSysClient, Delegations

        links = [
            row for row in Delegations(self.store).list() if row["agent"] == self.name
        ][-10:]
        results = []
        for row in links:
            try:
                task = AtSysClient(row["endpoint"]).status(row["upstream_id"])
                results.append(
                    {
                        **row,
                        "recorded_status": task["status"],
                        "updated_at": task.get("updatedAt"),
                        "source": "AtSys recorded state; not proof of a live worker",
                        "checked_at": stamp(),
                    }
                )
            except (OSError, ValueError, RuntimeError):
                results.append(
                    {
                        **row,
                        "recorded_status": "unreachable",
                        "checked_at": stamp(),
                        "next": "Use this agent's Supervision settings to check its service; no task was restarted",
                    }
                )
        return results

    def supervision_report(self, task_id: str) -> dict:
        """Read the durable report for one of your own task IDs, even when private AtSys is stopped."""
        from atbots.platform.integrations import AtSysClient, Delegations
        from atbots.platform.supervision_service import private_report

        link = next(
            (
                row
                for row in Delegations(self.store).list()
                if row["agent"] == self.name and row["upstream_id"] == task_id
            ),
            None,
        )
        if link is None:
            return {
                "status": "not_found",
                "next": "Use supervision_tasks to identify your own task ID",
            }
        try:
            try:
                report = AtSysClient(link["endpoint"]).report(task_id)
            except (OSError, ValueError, RuntimeError):
                report = private_report(self.store, self.name, task_id)
            text = report.get("markdown", "")
            screen_message(text)
            return {
                "agent": self.name,
                "task_id": task_id,
                "status": report.get("status"),
                "workflow_accepted": report.get("workflowAccepted"),
                "digest": report.get("digest"),
                "source": "AtSys durable report, not the agent's own success assertion",
                "markdown": text[:6000],
                "truncated": len(text) > 6000,
            }
        except (OSError, ValueError, RuntimeError):
            return {
                "status": "unavailable",
                "next": "Inspect this task's own AtSys report; do not infer completion or disclose restricted report content",
            }

    def request_supervision_action(
        self, task_id: str, action: Literal["pause", "resume", "stop"]
    ) -> dict:
        """Propose an operator-approved control action for one of your own tasks."""
        from atbots.platform.control import ControlPlan
        from atbots.platform.integrations import Delegations
        from atbots.platform.jobs import Operations

        link = next(
            (
                row
                for row in Delegations(self.store).list()
                if row["agent"] == self.name and row["upstream_id"] == task_id
            ),
            None,
        )
        if link is None:
            return {
                "status": "not_found",
                "next": "Use supervision_tasks to choose one of your own task IDs",
            }
        plan = ControlPlan(
            action="supervision_" + action, name=self.name, delegation_id=link["id"]
        )
        identity = Operations(self.store).propose(
            {
                "plan": plan.model_dump(mode="json"),
                "revision": self.store.get(self.name).revision,
                "memory_digest": None,
            }
        )
        return {
            "agent": self.name,
            "task_id": task_id,
            "approval_required": identity,
            "applied": False,
        }

    def request_memory_change(self, action, record_id, text=None):
        """Operator-selected correction/forget proposal, bound to the current record."""
        import hashlib

        from atbots.platform.control import ControlPlan
        from atbots.platform.jobs import Operations, canonical

        if not isinstance(self.memory, AtMemMemory) or action not in {
            "correct",
            "forget",
        }:
            raise StoreError("Unsupported scoped memory operation")
        records = self.memory.inspect(record_id)
        if len(records) != 1:
            raise StoreError("Select a record belonging to this agent")
        if text is not None:
            screen_message(text)
        plan = ControlPlan(
            action="memory_" + action, name=self.name, record_id=record_id, message=text
        )
        identity = Operations(self.store).propose(
            {
                "plan": plan.model_dump(mode="json"),
                "revision": self.store.get(self.name).revision,
                "memory_digest": hashlib.sha256(
                    canonical(records).encode()
                ).hexdigest(),
            }
        )
        return {"agent": self.name, "approval_required": identity, "applied": False}

    def request_supervision(self, objective: str) -> dict:
        """Propose an AtSys task using this agent's operator-configured roles and grants."""
        from atbots.platform.control import ControlPlan
        from atbots.platform.integrations import SupervisedObjective
        from atbots.platform.jobs import Operations

        profile = supervision_profile(self.store, self.name)
        if profile is None:
            return {
                "started": False,
                "status": "setup_required",
                "next": "Open this agent's Settings → Supervision, choose roles and a real acceptance command, then approve the task",
            }
        screen_message(objective)
        plan = ControlPlan(
            action="supervise",
            name=self.name,
            message=objective,
            supervision=SupervisedObjective.model_validate(profile),
        )
        identity = Operations(self.store).propose(
            {
                "plan": plan.model_dump(mode="json"),
                "revision": self.store.get(self.name).revision,
                "memory_digest": None,
            }
        )
        return {
            "agent": self.name,
            "approval_required": identity,
            "started": False,
            "execution_owner": "AtSys",
        }

    def request_schedule(self, objective: str, at: str, timezone: str = "UTC") -> dict:
        """Propose a one-time task for this agent at an ISO time with timezone offset."""
        from datetime import datetime
        from datetime import timezone as datetime_timezone
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        from atbots.platform.control import ControlPlan
        from atbots.platform.jobs import Operations
        from atbots.platform.scheduler import aware

        screen_message(objective)
        try:
            ZoneInfo(timezone)
            if aware(at) <= datetime.now(datetime_timezone.utc):
                raise ValueError("Time must be in the future")
        except (ValueError, ZoneInfoNotFoundError):
            return {
                "scheduled": False,
                "status": "clarification_required",
                "next": "Ask the user for a future date, time and timezone, or use this agent's Schedule form",
            }
        plan = ControlPlan(
            action="schedule_create",
            name=self.name,
            message=objective,
            at=at,
            timezone=timezone,
        )
        identity = Operations(self.store).propose(
            {
                "plan": plan.model_dump(mode="json"),
                "revision": self.store.get(self.name).revision,
                "memory_digest": None,
            }
        )
        return {"agent": self.name, "scheduled": False, "approval_required": identity}

    def tools(self):
        if self.name == "control-room":
            return []
        tools = [
            self.inspect_environment,
            self.supervision_tasks,
            self.supervision_report,
            self.request_supervision_action,
            self.request_supervision,
            self.request_schedule,
        ]
        if self.memory is not None:
            tools.append(self.search_memory)
        if isinstance(self.memory, AtMemMemory):
            tools.append(self.request_remember)
        return tools


def supervision_profile(store, name):
    store.get(name)
    with store.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS agent_supervision(agent TEXT PRIMARY KEY,profile TEXT NOT NULL)"
        )
        row = db.execute(
            "SELECT profile FROM agent_supervision WHERE agent=?", (name,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def configure_supervision(store, name, profile):
    from atbots.platform.integrations import SupervisedObjective

    definition = store.get(name)
    contract = SupervisedObjective.model_validate(profile)
    screen_message(contract.model_dump_json())
    with store.turn_lock(name), store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM handoffs WHERE agent=?", (name,)).fetchone():
            raise StoreError("Agent has a fenced handoff; reconcile it first")
        updated = definition.model_copy(update={"revision": definition.revision + 1})
        if (
            db.execute(
                "UPDATE agents SET definition=?,revision=? WHERE id=? AND revision=?",
                (
                    updated.model_dump_json(),
                    updated.revision,
                    definition.id,
                    definition.revision,
                ),
            ).rowcount
            != 1
        ):
            raise StoreError("Agent configuration changed; reload settings")
        db.execute(
            "CREATE TABLE IF NOT EXISTS agent_supervision(agent TEXT PRIMARY KEY,profile TEXT NOT NULL)"
        )
        db.execute(
            "INSERT OR REPLACE INTO agent_supervision VALUES (?,?)",
            (name, contract.model_dump_json()),
        )
    return {"agent": name, "configured": True, "health": "not_checked"}
