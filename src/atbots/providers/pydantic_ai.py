"""Pydantic AI adapter for Ollama and OpenAI-compatible model servers."""

from __future__ import annotations

import importlib.util
import json
import os
import re
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from atbots.domain import ProviderResult
from atbots.extensions import load_pydantic_capabilities
from atbots.providers.ollama_ctx import ContextProvision, ensure_context_tag, model_installed


_THINK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)


class PydanticAIProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        endpoint: str,
        api_key_env: str | None = None,
        egress_class: str = "local",
        capability_refs: list[str] | None = None,
        kind: str = "ollama",
        num_ctx: int | None = None,
        retries: int = 2,
    ) -> None:
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost", "https://")):
            raise ValueError("provider endpoint must be loopback HTTP or HTTPS")
        self.name = name
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key_env = api_key_env
        self.egress_class = egress_class
        self.capability_refs = list(capability_refs or [])
        self.kind = kind
        self.num_ctx = num_ctx
        self.retries = max(0, retries)
        self._context: ContextProvision | None = None
        # Ollama rejects Pydantic AI's default tool-mode structured output with
        # "invalid message content type: <nil>", so a constrained decision must
        # be requested as a JSON schema. Servers that cannot do that get the
        # prompted mode instead; the working mode is remembered per provider.
        self._output_mode = "native"
        self.unavailable_reason: str | None = None

    @property
    def api_base(self) -> str:
        return self.endpoint if self.endpoint.endswith("/v1") else f"{self.endpoint}/v1"

    def context(self) -> ContextProvision:
        """Resolve, once, which tag serves inference and at what window."""
        if self._context is None:
            if self.kind != "ollama":
                # Only Ollama derives models from other models. A remote
                # OpenAI-compatible endpoint has its own fixed window.
                self._context = ContextProvision(self.model, None, False, None)
            else:
                self._context = ensure_context_tag(
                    endpoint=self.endpoint, model=self.model, num_ctx=self.num_ctx
                )
        return self._context

    @property
    def serving_model(self) -> str:
        return self.context().tag

    def available(self) -> bool:
        """Whether this provider can actually serve a request, and why not."""
        self.unavailable_reason = None
        if importlib.util.find_spec("pydantic_ai") is None:
            return self._unavailable("pydantic-ai is not installed")
        if self.api_key_env and not os.environ.get(self.api_key_env):
            return self._unavailable(f"{self.api_key_env} is not set")
        try:
            request = Request(f"{self.api_base}/models", method="GET")
            with urlopen(request, timeout=1.5) as response:
                if not 200 <= response.status < 300:
                    return self._unavailable(f"{self.api_base} returned {response.status}")
        except (OSError, URLError):
            return self._unavailable(f"no model server is listening on {self.api_base}")
        if self.kind != "ollama":
            return True
        # A reachable server is not a usable one. Ollama answers /v1/models for
        # every install, so without this check an unpulled model looks available
        # and then 404s on every step of the run.
        if model_installed(self.endpoint, self.model) is False:
            return self._unavailable(f"model is not installed: ollama pull {self.model}")
        return True

    def _unavailable(self, reason: str) -> bool:
        self.unavailable_reason = reason
        return False

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
        output_type: type | None = None,
    ) -> ProviderResult:
        # Lazy imports keep AtBot diagnostics and deterministic fallback usable
        # even before the optional model framework has been installed.
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        key = os.environ.get(self.api_key_env or "") or "local-not-secret"
        model = OpenAIChatModel(
            self.serving_model,
            provider=OpenAIProvider(base_url=self.api_base, api_key=key),
        )
        schema_instruction = ""
        if schema and output_type is None:
            schema_instruction = (
                "\nReturn only valid JSON matching this JSON Schema:\n"
                + json.dumps(schema, separators=(",", ":"), sort_keys=True)
            )
        system_prompt = system + schema_instruction
        if output_type is None:
            result = self._run(model, system_prompt, prompt, None)
            text = strip_reasoning(str(result.output))
            structured = json.loads(text) if schema else None
        else:
            try:
                result = self._run(model, system_prompt, prompt, output_type)
            except Exception:
                if self._output_mode != "native":
                    raise
                # The server could not honour a JSON-schema response format.
                # Fall back once, permanently, to asking for the shape in the
                # prompt and validating the reply.
                self._output_mode = "prompted"
                result = self._run(model, system_prompt, prompt, output_type)
            value = result.output
            structured = value.model_dump() if hasattr(value, "model_dump") else dict(value)
            text = json.dumps(structured, default=str, sort_keys=True)
        return ProviderResult(
            text=text,
            structured=structured,
            provider=self.name,
            model=self.serving_model,
            egress_class=self.egress_class,
        )

    def _run(self, model: Any, system: str, prompt: str, output_type: type | None) -> Any:
        from pydantic_ai import Agent, NativeOutput, PromptedOutput

        if output_type is None:
            requested: Any = str
        elif self._output_mode == "prompted":
            requested = PromptedOutput(output_type)
        else:
            # A JSON-schema response format lets the server constrain decoding
            # and lets Pydantic AI re-ask on a validation failure, which is what
            # keeps a 4B model inside the contract instead of near it.
            requested = NativeOutput(output_type)
        agent = Agent(
            model,
            output_type=requested,
            system_prompt=system,
            model_settings={"temperature": 0},
            retries=self.retries,
            capabilities=load_pydantic_capabilities(self.capability_refs),
        )
        return agent.run_sync(prompt)


def strip_reasoning(text: str) -> str:
    """Remove inline reasoning blocks emitted by small reasoning models.

    Ollama returns Qwen reasoning in a separate field, but llama.cpp and LM
    Studio are equally valid OpenAI-compatible endpoints and inline it.
    """
    cleaned = _THINK.sub("", text).strip()
    if not cleaned and text.strip():
        # An unterminated block means the whole reply was reasoning; keep the
        # tail rather than returning nothing.
        cleaned = re.sub(r"^.*<(?:think|thinking|reasoning)>", "", text, flags=re.S).strip()
    return cleaned
