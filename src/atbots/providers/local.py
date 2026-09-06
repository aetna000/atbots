"""No-download deterministic local degradation provider."""

from __future__ import annotations

import json
import re
from typing import Any

from atbots.domain import ProviderResult


class DeterministicLocalProvider:
    name = "deterministic-local"
    model = "atbot-rules-v1"
    egress_class = "local"

    def available(self) -> bool:
        return True

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
        output_type: type | None = None,
    ) -> ProviderResult:
        del system, output_type
        if schema and schema.get("title") == "AtBotFactExtraction":
            source = prompt.rsplit("<current-message>\n", 1)[-1].split(
                "\n</current-message>", 1
            )[0]
            fact = _explicit_fact(source)
            value = {"facts": [fact] if fact else []}
            return ProviderResult(
                text=json.dumps(value),
                structured=value,
                provider=self.name,
                model=self.model,
                egress_class=self.egress_class,
            )
        if schema and schema.get("title") == "AtBotTaskStep":
            value = {
                "action": "finish",
                "reason": "A local model is required for multi-step tool planning.",
                "tool": None,
                "arguments": {},
                "answer": "I can run memory operations safely, but install the configured local Qwen model for autonomous multi-step tasks.",
            }
            return ProviderResult(
                text=json.dumps(value), structured=value, provider=self.name,
                model=self.model, egress_class=self.egress_class,
            )
        memory = ""
        match = re.search(r"<atmem-context[^>]*>(.*?)</atmem-context>", prompt, re.S)
        if match:
            memory = " ".join(match.group(1).split())
        answer = (
            f"Based on governed memory: {memory}"
            if memory
            else "I do not have enough governed memory to answer that yet."
        )
        return ProviderResult(
            text=answer,
            structured=None,
            provider=self.name,
            model=self.model,
            egress_class=self.egress_class,
        )


def _explicit_fact(message: str) -> dict[str, Any] | None:
    text = " ".join(message.strip().split())
    lowered = text.casefold()
    if not text or text.endswith("?"):
        return None
    indicators = (
        "remember ",
        "i prefer ",
        "i like ",
        "my favorite ",
        "my timezone ",
        "my name ",
        "i am ",
        "i'm ",
    )
    if not any(value in lowered for value in indicators):
        return None
    return {
        "fact": text,
        "fact_key": None,
        "confidence": 0.75,
        "sensitivity": "personal",
        "entities": [],
        "suggested_action": "add",
        "related_record_ids": [],
    }
