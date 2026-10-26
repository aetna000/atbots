"""Versioned, credential-free definitions for persistent agents."""

from __future__ import annotations

import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RESERVED_NAMES = frozenset(
    [
        "auth",
        "init",
        "status",
        "doctor",
        "serve",
        "agents",
        "chat",
        "control",
        "run",
        "schedule",
        "deploy",
        "memory",
        "help",
        "ui",
        "runner",
        "jobs",
        "schedules",
        "browser",
        "skills",
        "export",
        "import",
        "cloud",
        "move",
        "state",
        "image-build",
        "supervision",
    ]
)


def agent_name(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value) or value in RESERVED_NAMES:
        raise ValueError(
            "Use 1–48 lowercase letters/digits/hyphens, starting with a letter; management names are reserved"
        )
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModelBinding(Contract):
    kind: Literal[
        "ollama", "openai-compatible", "chatgpt", "github-copilot", "anthropic"
    ] = "ollama"
    model: str = Field(default="qwen3:4b", min_length=1, max_length=160)
    endpoint: str = "http://127.0.0.1:11434"
    egress_class: Literal["local", "remote"] = "local"
    api_key_env: str | None = None
    auth_profile: str = "default"

    @field_validator("model")
    @classmethod
    def nonblank_model(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("An explicit, nonblank model ID is required")
        return value

    @field_validator("api_key_env")
    @classmethod
    def env_reference(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", value):
            raise ValueError("Use an environment-variable name, not a credential value")
        return value

    @field_validator("auth_profile")
    @classmethod
    def profile_reference(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
            raise ValueError("Invalid authentication profile")
        return value

    @model_validator(mode="after")
    def endpoint_policy(self) -> ModelBinding:
        url = urlsplit(self.endpoint)
        if (
            url.username
            or url.password
            or url.query
            or url.fragment
            or not url.hostname
        ):
            raise ValueError("Endpoint must not contain credentials, query or fragment")
        if self.kind in {"chatgpt", "github-copilot", "anthropic"}:
            if self.egress_class != "remote":
                raise ValueError("Account/API providers require explicit remote egress")
            return self
        local = url.hostname == "localhost"
        try:
            local = local or ipaddress.ip_address(url.hostname).is_loopback
        except ValueError:
            pass
        if url.scheme not in {"http", "https"} or (url.scheme == "http" and not local):
            raise ValueError("Endpoint requires HTTPS, except for loopback HTTP")
        if self.egress_class == "local" and not local:
            raise ValueError("Non-loopback endpoints require explicit remote egress")
        return self


class RunLimits(Contract):
    requests: int = Field(default=12, ge=1, le=100)
    total_tokens: int = Field(default=32000, ge=100, le=1_000_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class Capabilities(Contract):
    browser_domains: list[str] = Field(default_factory=list, max_length=32)
    browser_actions: list[
        Literal["navigate", "snapshot", "screenshot", "click", "type"]
    ] = Field(default_factory=list)
    browser_headed: bool = False
    vision: bool = False
    file_read: bool = False
    file_create: bool = False
    skills: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("browser_domains")
    @classmethod
    def exact_domains(cls, values):
        for value in values:
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,252}", value) or ".." in value:
                raise ValueError(
                    "Browser grants use exact lowercase hostnames, not URLs/wildcards"
                )
        return values


class AgentDefinition(Contract):
    format: Literal["atbots-agent-v1"] = "atbots-agent-v1"
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    name: str
    revision: int = Field(default=1, ge=1)
    created_at: str
    instructions: str = Field(
        default="You are a helpful personal agent. Be explicit about uncertainty and tool failures.",
        max_length=16000,
    )
    binding: ModelBinding = Field(default_factory=ModelBinding)
    limits: RunLimits = Field(default_factory=RunLimits)
    remote_allowed: bool = False
    state: Literal["active", "paused", "retired"] = "active"
    capabilities: Capabilities = Field(default_factory=Capabilities)

    _name = field_validator("name")(agent_name)

    @field_validator("instructions")
    @classmethod
    def credential_free_instructions(cls, value: str) -> str:
        from atmem.extract.validation import screen_content

        if (
            "secret_material_detected"
            in screen_content(value, trusted=True).reason_codes
        ):
            raise ValueError("Instructions must not contain recognizable credentials")
        return value

    @model_validator(mode="after")
    def explicit_remote_grant(self) -> AgentDefinition:
        if self.binding.egress_class == "remote" and not self.remote_allowed:
            raise ValueError("Remote model selection requires remote_allowed=true")
        return self
