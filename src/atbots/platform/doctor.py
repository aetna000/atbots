"""Read-only setup checks; never provision credentials or call a paid model."""

import importlib.util
import os
import shutil
from importlib.metadata import PackageNotFoundError, version


def doctor(store):
    checks = []

    def check(name, state, detail):
        checks.append({"check": name, "state": state, "detail": detail})

    with store.connect() as db:
        check(
            "registry",
            "ok" if db.execute("PRAGMA quick_check").fetchone()[0] == "ok" else "error",
            "SQLite quick_check",
        )
    check(
        "disk",
        "ok" if shutil.disk_usage(store.root).free > 250_000_000 else "error",
        "At least 250 MB of local free space required",
    )
    for package in (
        "atbots",
        "atmem",
        "pydantic-ai-slim",
        "playwright",
        "APScheduler",
        "atsys",
        "atflows",
    ):
        try:
            check(package, "installed", version(package))
        except PackageNotFoundError:
            check(
                package,
                "optional_missing",
                "Install the corresponding AtBots extra if enabled",
            )
    for definition in store.list():
        binding = definition.binding
        if binding.api_key_env:
            check(
                definition.name + ":credential-reference",
                "present" if os.environ.get(binding.api_key_env) else "missing",
                "Environment reference checked; value never displayed",
            )
        if binding.kind in {"chatgpt", "github-copilot", "anthropic"}:
            check(
                definition.name + ":authentication",
                "not_probed",
                "Run atbots auth status for the configured account profile; no inference was attempted",
            )
        if definition.capabilities.browser_domains:
            available = importlib.util.find_spec("playwright") is not None
            check(
                definition.name + ":browser",
                "installed" if available else "missing",
                "Install atbots[browser] and python -m playwright install chromium; macOS Chrome can be reused. Login and vision require separate acceptance.",
            )
        check(
            definition.name + ":workspace",
            "ok" if (store.workspace(definition.name) / "files").is_dir() else "error",
            "Scoped workspace exists; not an OS execution sandbox",
        )
    check(
        "scheduler",
        "desktop_managed_or_explicit_runner",
        "Opening atbots starts its local background runner. PC sleep stops progress. OS boot integration remains explicit; do not start a second runner for the same root.",
    )
    check(
        "integrations",
        "not_probed",
        "AtSys/AtFlows/cloud require explicit endpoints and credentials; no service was mutated",
    )
    return {
        "ready": not any(c["state"] in {"error", "missing"} for c in checks),
        "checks": checks,
        "model_inference_tested": False,
        "cloud_permissions_tested": False,
    }
