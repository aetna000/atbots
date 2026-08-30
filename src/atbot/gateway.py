"""The only AtBot module allowed to import AtMem authority APIs."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from atmem import Memory
from atmem.contracts import (
    AuthorityScope,
    ContextPackage,
    ContextRequest,
    EligibleCandidateSet,
    ExposureConfirmation,
    ExposureReceipt,
    MemoryAdmission,
    MemoryProposal,
    RecallRequest,
    SourceCaptureRequest,
    SourceCaptureResult,
    capabilities,
)

from atbot.config import AtBotConfig


class AtMemGateway:
    def __init__(self, config: AtBotConfig) -> None:
        self.config = config

    @property
    def scope(self) -> AuthorityScope:
        return AuthorityScope(
            subject_id=self.config.subject_id,
            agent_id=self.config.agent_id,
            workspace_id=self.config.workspace_id,
        )

    @contextmanager
    def _memory(self) -> Iterator[Memory]:
        memory = Memory(self.config.memory_file, graph_recall=True)
        try:
            yield memory
        finally:
            memory.close()

    def initialize(self) -> dict[str, object]:
        self.config.memory_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._memory() as memory:
            vector = memory.sync_default_vectors(self.config.subject_id)
            advertised = capabilities()
        return {"memory_path": str(self.config.memory_file), "vector": vector, "capabilities": advertised}

    def capture(self, request: SourceCaptureRequest) -> SourceCaptureResult:
        with self._memory() as memory:
            return memory.capture_source(request)

    def propose(self, proposal: MemoryProposal) -> MemoryAdmission:
        with self._memory() as memory:
            return memory.submit_proposal(proposal)

    def candidates(self, request: RecallRequest) -> EligibleCandidateSet:
        with self._memory() as memory:
            return memory.eligible_candidates(request)

    def prepare(self, request: ContextRequest) -> ContextPackage:
        with self._memory() as memory:
            return memory.prepare_context_v1(request)

    def confirm(self, confirmation: ExposureConfirmation) -> ExposureReceipt:
        with self._memory() as memory:
            return memory.confirm_exposure_v1(confirmation)

    def verify(self) -> dict[str, object]:
        with self._memory() as memory:
            return {
                "audit": memory.verify(self.config.subject_id),
                "capabilities": capabilities(),
                "vector": memory.sync_default_vectors(self.config.subject_id),
            }

    def inspect_records(self) -> list[dict[str, object]]:
        """Human-facing projection; raw storage remains owned by AtMem."""
        with self._memory() as memory:
            return memory.list(self.config.subject_id, include_inactive=True)
