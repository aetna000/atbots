"""Load user-configured Pydantic AI capabilities from modules or Python files."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any


def load_object(reference: str) -> Any:
    """Load ``module:attribute`` or ``/path/to/file.py:attribute``."""
    source, separator, attribute = reference.rpartition(":")
    if not separator or not source or not attribute:
        raise ValueError(
            f"invalid capability reference {reference!r}; expected module:object or file.py:object"
        )
    if source.endswith(".py") or "/" in source or "\\" in source:
        path = Path(source).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"capability source is not a file: {path}")
        module_name = f"_atbots_extension_{abs(hash(path))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError(f"cannot import capability source: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(source)
    try:
        return getattr(module, attribute)
    except AttributeError as exc:
        raise ValueError(f"capability object {attribute!r} was not found in {source!r}") from exc


def load_pydantic_capabilities(references: list[str]) -> tuple[Any, ...]:
    """Load and validate configured Pydantic AI AgentCapability instances."""
    if not references:
        return ()
    from pydantic_ai.capabilities import AbstractCapability

    loaded = tuple(load_object(reference) for reference in references)
    for reference, capability in zip(references, loaded, strict=True):
        if not isinstance(capability, AbstractCapability):
            raise ValueError(
                f"{reference!r} is not a Pydantic AI AgentCapability instance"
            )
    return loaded
