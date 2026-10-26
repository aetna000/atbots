"""Scoped AtMem authority adapter; history is not canonical memory."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from atbots.config import AtBotConfig
from atbots.gateway import AtMemGateway
from atbots.platform.store import AgentStore


class MemoryPolicyError(ValueError):
    pass


def screen_message(text: str) -> None:
    # Known patterns only: this is not comprehensive sensitive-data detection.
    from atmem.extract.validation import screen_content

    if "secret_material_detected" in screen_content(text, trusted=True).reason_codes:
        raise MemoryPolicyError(
            "Recognizable credential material was refused before model/history/memory capture; use authentication setup instead"
        )


@dataclass(frozen=True)
class MemoryContext:
    text: str = ""
    package: Any = None
    shared: tuple = ()


class MemoryPort(Protocol):
    def context(self, query: str, *, egress: str) -> MemoryContext: ...
    def confirm(self, context: MemoryContext, run_id: str) -> str | None: ...
    def remember(self, text: str) -> dict: ...


class AtMemMemory:
    def __init__(self, store: AgentStore, name: str):
        self.store, self.name = store, name
        definition = store.get(name)
        self.gateway = AtMemGateway(
            AtBotConfig(
                memory_path=str(store.workspace(name) / "memory.db"),
                subject_id=f"owner-{definition.id}",
                agent_id=f"agent-{definition.id}",
                workspace_id=f"workspace-{definition.id}",
                providers=[],
            )
        )

    def context(
        self, query: str, *, egress: str, include_shared: bool = True
    ) -> MemoryContext:
        from atmem.contracts import ContextRequest, RecallRequest

        candidates = self.gateway.candidates(
            RecallRequest(
                request_id=f"recall-{uuid.uuid4().hex}",
                scope=self.gateway.scope,
                query=query,
                limit=8,
                min_score=0.25,
                egress_class=egress,
            )
        )
        package = (
            self.gateway.prepare(
                ContextRequest(
                    context_id=f"context-{uuid.uuid4().hex}",
                    scope=self.gateway.scope,
                    candidate_set_id=candidates.candidate_set_id,
                    record_ids=tuple(c.record_id for c in candidates.candidates),
                )
            )
            if candidates.candidates
            else None
        )
        shared = []
        if include_shared:
            for name in self.store.shared_sources(self.name)[:3]:
                other = AtMemMemory(self.store, name)
                context = other.context(query, egress=egress, include_shared=False)
                if context.text:
                    shared.append((name, context))
        texts = ([package.context] if package else []) + [
            f"Shared by {name}:\n{ctx.text}" for name, ctx in shared
        ]
        return MemoryContext(
            text="\n".join(texts), package=package, shared=tuple(shared)
        )

    def confirm(self, context: MemoryContext, run_id: str) -> str | None:
        from atmem.contracts import ExposureConfirmation

        package = context.package
        receipts = []
        for name, shared in context.shared:
            if name not in self.store.shared_sources(self.name):
                raise MemoryPolicyError(
                    "Memory sharing was revoked during this turn; prior exposure cannot be undone"
                )
            receipt = AtMemMemory(self.store, name).confirm(shared, run_id)
            if receipt:
                receipts.append(receipt)
        if package is not None:
            receipts.append(
                self.gateway.confirm(
                    ExposureConfirmation(
                        confirmation_id=f"exposure-{uuid.uuid4().hex}",
                        preparation_id=package.preparation_id,
                        scope=self.gateway.scope,
                        context_sha256=package.context_sha256,
                        host_run_id=run_id,
                    )
                ).receipt_id
            )
        return ",".join(receipts) or None

    def capture_user(self, text: str) -> dict:
        screen_message(text)
        with self.gateway._memory() as memory:
            result = memory.remember(
                self.gateway.scope.subject_id,
                message=text,
                raw={"authority_scope": self.gateway.scope.to_dict()},
                actor="atbots-user-turn",
            )
        return {
            "captured_records": len(result.get("records", [])),
            "refused": result.get("refused", []),
        }

    def inspect(self, record_id: str | None = None) -> list[dict]:
        rows = self.gateway.inspect_records()
        if record_id is not None:
            rows = [row for row in rows if row["id"] == record_id]
            if not rows:
                raise MemoryPolicyError("Memory record is not in this agent's scope")
        return rows

    def correct(self, record_id: str, text: str) -> dict:
        screen_message(text)
        self.inspect(record_id)
        with self.gateway._memory() as memory:
            return memory.correct_record(
                self.gateway.scope.subject_id, record_id, text, actor="atbots-operator"
            )

    def forget(self, record_id: str) -> dict:
        self.inspect(record_id)
        with self.gateway._memory() as memory:
            return memory.forget_record(
                self.gateway.scope.subject_id, record_id, actor="atbots-operator"
            )

    def remember(self, text: str) -> dict:
        from atmem.contracts import (
            InterpreterIdentity,
            MemoryProposal,
            SourceBinding,
            SourceCaptureRequest,
        )
        from atmem.extract.validation import screen_content

        screen_message(text)
        if not text.strip() or len(text) > 2000:
            raise MemoryPolicyError("Explicit memory must contain 1–2000 characters")
        screening = screen_content(text, trusted=True)
        if not screening.admissible:
            return {
                "decision": "rejected",
                "reason_codes": list(screening.reason_codes),
            }
        identity = uuid.uuid4().hex
        source_id = f"source-{identity}"
        captured = self.gateway.capture(
            SourceCaptureRequest(
                source_id=source_id,
                idempotency_key=f"capture-{identity}",
                scope=self.gateway.scope,
                message=text,
                retain_body=False,
                binding_method="operator_authenticated",
                binding_assurance="verified_by_atmem",
            )
        )
        return self.gateway.propose(
            MemoryProposal(
                proposal_id=f"proposal-{identity}",
                idempotency_key=f"proposal-{identity}",
                scope=self.gateway.scope,
                fact=text,
                confidence=1.0,
                source_ids=(source_id,),
                source_binding=SourceBinding(
                    method="operator_authenticated",
                    source_sha256=captured.source_sha256,
                    assurance="verified_by_atmem",
                ),
                interpreter=InterpreterIdentity(
                    provider="operator",
                    model="explicit-user-memory",
                    prompt_version="explicit-memory-v1",
                    assurance="rule_extracted",
                    egress_class="local",
                ),
            )
        ).to_dict()
