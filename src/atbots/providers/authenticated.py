"""Native Pydantic AI model wiring; authentication is not a second agent loop."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from atbots.auth import (
    AuthError,
    CredentialStore,
    auth_status,
    chatgpt_source,
    credential_state,
    native_module,
    profile_lock,
    validate_profile,
)
from atbots.config import ProviderConfig
from atbots.domain import ProviderResult
from atbots.providers.pydantic_ai import PydanticAIProvider


class AuthenticatedProvider(PydanticAIProvider):
    def __init__(
        self, row: ProviderConfig, *, capability_refs: list[str], retries: int
    ) -> None:
        if row.egress_class != "remote":
            raise ValueError("Account/API providers require explicit remote egress")
        if row.kind != "anthropic":
            validate_profile(row.kind, row.auth_profile)
        super().__init__(
            name=row.name,
            model=row.model,
            endpoint="https://api.openai.com",
            kind=row.kind,
            egress_class="remote",
            retries=retries,
            capability_refs=capability_refs,
        )
        self.auth_profile = row.auth_profile
        self.api_key_env = row.api_key_env
        # Prompted structured output works across these native models without
        # retrying arbitrary authentication failures as a schema-format fallback.
        self._output_mode = "prompted"

    def available(self) -> bool:
        self.unavailable_reason = None
        if self.kind == "anthropic":
            if importlib.util.find_spec("anthropic") is None:
                return self._unavailable(
                    'Install native API support: python -m pip install "atbots[anthropic]"'
                )
            if not self.api_key_env or not os.environ.get(self.api_key_env):
                return self._unavailable(
                    "Configure api_key_env with your Anthropic API key"
                )
            return True  # configured, not live entitlement verification
        try:
            native_module(self.kind)
            state = auth_status(self.kind, self.auth_profile)
        except AuthError as exc:
            return self._unavailable(str(exc))
        if state["state"] != "saved":
            return self._unavailable(
                f"Authentication is {state['state']}; run atbots auth login {self.kind}"
            )
        return True

    @asynccontextmanager
    async def model_context(self):
        """Reuse native provider lifecycle for both legacy and platform agents.

        The caller holds profile_lock for OAuth load/refresh/inference.
        """
        if self.kind == "anthropic":
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider

            if not self.api_key_env or not os.environ.get(self.api_key_env):
                raise AuthError("Anthropic API key is not configured")
            provider = AnthropicProvider(api_key=os.environ[self.api_key_env])
            model = AnthropicModel(self.model, provider=provider)
        else:
            store = CredentialStore()
            value = store.load(self.kind, self.auth_profile)
            if credential_state(self.kind, value) != "saved":
                raise AuthError(
                    f"{self.kind} requires sign-in with inference permission"
                )
            if self.kind == "chatgpt":
                from pydantic_ai.models.openai import OpenAIResponsesModel

                native = native_module(self.kind)
                provider = native.OpenAIChatGPTProvider(
                    credential_source=chatgpt_source(self.auth_profile, store)
                )
                model = OpenAIResponsesModel(self.model, provider=provider)
            else:
                from pydantic_ai.models.github_copilot import GitHubCopilotModel

                native = native_module(self.kind)
                provider = native.GitHubCopilotProvider(
                    api_key=value["credentials"]["access_token"]
                )
                model = GitHubCopilotModel(self.model, provider=provider)
        async with provider:
            yield model

    async def _invoke(self, system: str, prompt: str, output_type: type | None) -> Any:
        async with self.model_context() as model:
            return await self._build_agent(model, system, output_type).run(prompt)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
        output_type: type | None = None,
    ) -> ProviderResult:
        if schema and output_type is None:
            system += "\nReturn only JSON matching this schema:\n" + json.dumps(schema)
        try:
            if self.kind == "anthropic":
                result = asyncio.run(self._invoke(system, prompt, output_type))
            else:
                # Keep load, refresh, persistence and inference serialized. A
                # rotating refresh token must never be replayed by another process.
                with profile_lock(self.kind, self.auth_profile):
                    result = asyncio.run(self._invoke(system, prompt, output_type))
            value = result.output
            structured = (
                (value.model_dump() if hasattr(value, "model_dump") else dict(value))
                if output_type
                else (json.loads(value) if schema else None)
            )
            text = json.dumps(structured, sort_keys=True) if output_type else str(value)
            usage = result.usage
            return ProviderResult(
                text=text,
                structured=structured,
                provider=self.name,
                model=self.model,
                egress_class="remote",
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        except AuthError:
            raise
        except Exception:  # noqa: BLE001 - never expose provider request/response secrets
            # SDK exceptions may contain request/response bodies and tokens.
            raise AuthError(
                f"{self.kind} request failed; check sign-in, model entitlement and provider limits. No fallback request was made"
            ) from None
