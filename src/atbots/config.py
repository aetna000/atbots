"""Small explicit AtBot configuration with safe local-first defaults."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path.home() / ".atbots"
DEFAULT_CONFIG = DEFAULT_ROOT / "config.json"
LEGACY_DEFAULT_CONFIG = Path.home() / ".atbot" / "config.json"


@dataclass(slots=True)
class ProviderConfig:
    name: str = "local"
    kind: str = "ollama"
    model: str = "qwen3:4b"
    endpoint: str = "http://127.0.0.1:11434"
    api_key_env: str | None = None
    egress_class: str = "local"


@dataclass(slots=True)
class AtBotConfig:
    format: str = "atbot-config-v1"
    memory_path: str = str(DEFAULT_ROOT / "atmem.db")
    subject_id: str = "local-user"
    agent_id: str = "atbot-main"
    workspace_id: str = "private"
    profile: str = "memory-companion"
    host: str = "127.0.0.1"
    port: int = 8770
    recent_message_limit: int = 10
    remote_egress_allowed: bool = False
    max_task_steps: int = 8
    allowed_tools: list[str] = field(default_factory=lambda: ["memory_recall"])
    skill_directories: list[str] = field(default_factory=list)
    pydantic_capabilities: list[str] = field(default_factory=list)
    providers: list[ProviderConfig] = field(default_factory=lambda: [ProviderConfig()])

    @property
    def memory_file(self) -> Path:
        return Path(self.memory_path).expanduser().resolve(strict=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AtBotConfig":
        if value.get("format") != "atbot-config-v1":
            raise ValueError("unsupported AtBot config format")
        providers = [ProviderConfig(**row) for row in value.get("providers") or []]
        return cls(
            **{
                key: item
                for key, item in value.items()
                if key not in {"providers"}
            },
            providers=providers or [ProviderConfig()],
        )


def load_config(path: str | Path = DEFAULT_CONFIG) -> AtBotConfig:
    source = Path(path).expanduser()
    if source == DEFAULT_CONFIG and not source.is_file() and LEGACY_DEFAULT_CONFIG.is_file():
        source = LEGACY_DEFAULT_CONFIG
    if not source.is_file():
        raise FileNotFoundError(
            f"AtBots is not configured: {source}. Run `atbots init` first."
        )
    return AtBotConfig.from_dict(json.loads(source.read_text(encoding="utf-8")))


def save_config(config: AtBotConfig, path: str | Path = DEFAULT_CONFIG) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(target)
    return target
