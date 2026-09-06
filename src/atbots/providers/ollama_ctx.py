"""Give a local Ollama model the context window the user configured.

Measured against a live Ollama server: ``options.num_ctx`` sent to the
OpenAI-compatible ``/v1/chat/completions`` endpoint is dropped, and the model
loads at the 4096-token server default. The native ``/api/chat`` endpoint honours
it, but a following OpenAI-compatible request evicts that instance and reloads at
the default, so preloading does not survive. Only a model whose own parameters
carry ``num_ctx`` loads at the requested window over the OpenAI-compatible path.

So AtBots derives one: a tiny tag built ``from`` the configured model with
``num_ctx`` baked in. It reuses the parent model's existing layers, downloads
nothing, and is created once.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import URLError
from urllib.request import Request, urlopen


SUFFIX = "-atbots-ctx"


@dataclass(frozen=True, slots=True)
class ContextProvision:
    """The tag to run inference against, and how it was obtained."""

    tag: str
    num_ctx: int | None
    provisioned: bool
    reason: str | None = None


_CACHE: dict[tuple[str, str, int], ContextProvision] = {}


def native_root(endpoint: str) -> str:
    """Native API root for an endpoint that may be written with a /v1 suffix."""
    root = endpoint.rstrip("/")
    return root[: -len("/v1")] if root.endswith("/v1") else root


def context_tag(model: str, num_ctx: int) -> str:
    return f"{model}{SUFFIX}{num_ctx}"


def ensure_context_tag(
    *, endpoint: str, model: str, num_ctx: int | None, timeout: float = 60.0
) -> ContextProvision:
    """Return the tag to use, creating the derived one if it does not exist yet.

    Never raises: a server that is unreachable or too old to derive a model is a
    reason to run at the default window, not a reason to fail the user's task.
    """
    if not num_ctx or num_ctx <= 0:
        return ContextProvision(model, None, False, None)
    if SUFFIX in model:
        # The user pinned a derived tag themselves; respect it as-is.
        return ContextProvision(model, num_ctx, False, "model already pinned")
    root = native_root(endpoint)
    key = (root, model, num_ctx)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = _provision(root=root, model=model, num_ctx=num_ctx, timeout=timeout)
    _CACHE[key] = result
    return result


def _provision(*, root: str, model: str, num_ctx: int, timeout: float) -> ContextProvision:
    tag = context_tag(model, num_ctx)
    installed = _installed_tags(root, timeout=min(timeout, 5.0))
    if installed is None:
        return ContextProvision(model, None, False, "ollama is not reachable")
    if tag in installed:
        return ContextProvision(tag, num_ctx, True, None)
    if model not in installed:
        return ContextProvision(
            model, None, False, f"model is not installed: ollama pull {model}"
        )
    error = _create(root, tag=tag, model=model, num_ctx=num_ctx, timeout=timeout)
    if error is not None:
        return ContextProvision(model, None, False, error)
    return ContextProvision(tag, num_ctx, True, None)


def model_installed(endpoint: str, model: str, *, timeout: float = 2.0) -> bool | None:
    """Whether the tag exists locally. None when the server cannot be asked."""
    installed = _installed_tags(native_root(endpoint), timeout=timeout)
    if installed is None:
        return None
    return model in installed


def _installed_tags(root: str, *, timeout: float) -> set[str] | None:
    try:
        with urlopen(Request(f"{root}/api/tags", method="GET"), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError):
        return None
    names: set[str] = set()
    for row in payload.get("models") or []:
        name = row.get("name") or row.get("model")
        if not name:
            continue
        names.add(name)
        # Ollama reports "qwen3:4b" as "qwen3:4b"; bare names carry ":latest".
        if name.endswith(":latest"):
            names.add(name[: -len(":latest")])
    return names


def _create(root: str, *, tag: str, model: str, num_ctx: int, timeout: float) -> str | None:
    body = json.dumps(
        {"model": tag, "from": model, "parameters": {"num_ctx": num_ctx}}
    ).encode("utf-8")
    request = Request(
        f"{root}/api/create",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            # /api/create streams newline-delimited progress; the failure is
            # reported inside the stream rather than as an HTTP status.
            for line in response:
                text = line.decode("utf-8").strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except ValueError:
                    continue
                if row.get("error"):
                    return f"could not derive {tag}: {row['error']}"
    except (OSError, URLError) as exc:
        return f"could not derive {tag}: {exc}"
    return None
