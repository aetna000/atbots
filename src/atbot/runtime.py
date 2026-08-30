"""AtBot memory-centre and task-capable agent runtime."""

from __future__ import annotations

from collections import deque
import hashlib
import uuid

from atmem.contracts import (
    ContextRequest,
    ExposureConfirmation,
    InterpreterIdentity,
    MemoryProposal,
    RecallRequest,
    SourceBinding,
    SourceCaptureRequest,
)

from atbot.config import AtBotConfig
from atbot.domain import ChatResult, ProviderResult
from atbot.extraction import extract_facts
from atbot.gateway import AtMemGateway
from atbot.prompts import build_chat_prompt
from atbot.providers.router import ModelRouter


class AtBotRuntime:
    def __init__(self, config: AtBotConfig) -> None:
        self.config = config
        self.gateway = AtMemGateway(config)
        self.router = ModelRouter(config)
        self._recent: deque[tuple[str, str]] = deque(maxlen=config.recent_message_limit)

    def remember(self, message: str, *, session_id: str = "cli") -> tuple[dict[str, object], ...]:
        clean = " ".join(message.split())
        if not clean:
            raise ValueError("message is required")
        provider = self.router.select(sensitivity="personal", remote=False)
        facts = extract_facts(provider, clean)
        if not facts:
            return ()
        run_id = uuid.uuid4().hex
        source_id = f"src_{run_id}"
        capture = self.gateway.capture(
            SourceCaptureRequest(
                source_id=source_id,
                idempotency_key=f"capture:{run_id}",
                scope=self.gateway.scope,
                message=clean,
                session_id=session_id,
                turn_id=run_id,
                binding_method="operator_authenticated" if session_id == "cli" else "host_authenticated_turn",
                binding_assurance="verified_by_atmem" if session_id == "cli" else "host_authenticated",
            )
        )
        results: list[dict[str, object]] = []
        for index, fact in enumerate(facts):
            proposal = MemoryProposal(
                proposal_id=f"prop_{run_id}_{index}",
                idempotency_key=f"proposal:{run_id}:{index}",
                scope=self.gateway.scope,
                fact=fact.fact,
                fact_key=fact.fact_key,
                confidence=fact.confidence,
                sensitivity=fact.sensitivity,
                entities=fact.entities,
                suggested_action=fact.suggested_action,
                related_record_ids=fact.related_record_ids,
                source_ids=(source_id,),
                source_binding=SourceBinding(
                    method="operator_authenticated" if session_id == "cli" else "host_authenticated_turn",
                    source_sha256=capture.source_sha256,
                    assurance="verified_by_atmem" if session_id == "cli" else "host_authenticated",
                ),
                interpreter=InterpreterIdentity(
                    provider=provider.name,
                    model=provider.model,
                    prompt_version="atbot-extract-v1",
                    assurance="rule_extracted" if provider.name == "deterministic-local" else "model_interpreted",
                    egress_class=provider.egress_class,
                ),
                session_id=session_id,
                turn_id=run_id,
            )
            admission = self.gateway.propose(proposal)
            results.append(admission.to_dict())
        return tuple(results)

    def recall(self, query: str, *, limit: int = 8, remote: bool = False):
        provider = self.router.select(remote=remote)
        return self.gateway.candidates(
            RecallRequest(
                request_id=f"req_{uuid.uuid4().hex}",
                scope=self.gateway.scope,
                query=query,
                limit=limit,
                egress_class=provider.egress_class,
                reranker_provider=provider.name,
                reranker_model=provider.model,
                min_score=_minimum_relevance(query),
            )
        )

    def chat(self, message: str, *, session_id: str = "main", remote: bool = False) -> ChatResult:
        clean = " ".join(message.split())
        if not clean:
            raise ValueError("message is required")
        run_id = uuid.uuid4().hex
        admissions = self.remember(clean, session_id=session_id)
        provider = self.router.select(sensitivity="personal", remote=remote)
        candidate_set = self.gateway.candidates(
            RecallRequest(
                request_id=f"req_{run_id}",
                scope=self.gateway.scope,
                query=clean,
                limit=8,
                egress_class=provider.egress_class,
                reranker_provider=provider.name,
                reranker_model=provider.model,
                min_score=_minimum_relevance(clean),
            )
        )
        context = None
        receipt = None
        if candidate_set.candidates:
            context = self.gateway.prepare(
                ContextRequest(
                    context_id=f"ctx_{run_id}",
                    candidate_set_id=candidate_set.candidate_set_id,
                    scope=self.gateway.scope,
                    record_ids=tuple(row.record_id for row in candidate_set.candidates),
                )
            )
        bundle = build_chat_prompt(clean, context.context if context else "")
        if context and _is_memory_overview(clean):
            lines = "\n".join(f"- {row.content}" for row in candidate_set.candidates)
            output = ProviderResult(
                text=f"I remember:\n{lines}",
                structured=None,
                provider="atbot-policy",
                model="memory-overview-v1",
                egress_class="none",
            )
        elif context is None and _asks_for_personal_knowledge(clean):
            output = ProviderResult(
                text="I don't have a governed memory of that yet.",
                structured=None,
                provider="atbot-policy",
                model="memory-absence-v1",
                egress_class="none",
            )
        else:
            output = provider.complete(system=bundle.system, prompt=bundle.prompt)
        if context:
            receipt = self.gateway.confirm(
                ExposureConfirmation(
                    confirmation_id=f"confirm_{run_id}",
                    preparation_id=context.preparation_id,
                    scope=self.gateway.scope,
                    context_sha256=context.context_sha256,
                    host_run_id=run_id,
                )
            )
        self._recent.append(("user", clean))
        self._recent.append(("assistant", output.text))
        trace = (
            {"stage": "inference", "proposal_count": len(admissions)},
            {"stage": "retrieval", "candidate_count": len(candidate_set.candidates)},
            {
                "stage": "generation",
                "response_sha256": "sha256:" + hashlib.sha256(output.text.encode()).hexdigest(),
                "context_sha256": context.context_sha256 if context else None,
            },
        )
        return ChatResult(
            text=output.text,
            run_id=run_id,
            provider=output.provider,
            model=output.model,
            memory_record_ids=context.record_ids if context else (),
            context_receipt_id=receipt.receipt_id if receipt else None,
            cache_key=bundle.cache_key,
            trace=trace,
        )

    def recent(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._recent)


def _minimum_relevance(query: str) -> float:
    text = " ".join(query.casefold().split())
    overview_phrases = (
        "what do you remember",
        "what you remember",
        "everything you remember",
        "list my memories",
        "show my memories",
        "what do you know about me",
    )
    return 0.0 if any(phrase in text for phrase in overview_phrases) else 0.25


def _is_memory_overview(query: str) -> bool:
    return _minimum_relevance(query) == 0.0


def _asks_for_personal_knowledge(query: str) -> bool:
    text = " ".join(query.casefold().split())
    phrases = (
        "my opinion",
        "my preference",
        "my favorite",
        "my favourite",
        "do i prefer",
        "what do i like",
        "what did i say",
        "what is my",
        "who am i",
    )
    return any(phrase in text for phrase in phrases)
