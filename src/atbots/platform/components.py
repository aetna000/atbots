"""Inspect and explicitly upgrade allowlisted components in this Python environment."""

import json
import re
import subprocess
import sys
import threading
import uuid
from importlib.metadata import PackageNotFoundError, distributions, version
from urllib.request import ProxyHandler, build_opener

from filelock import FileLock

from atbots.platform.integrations import AtSysClient, Delegations, NoRedirect
from atbots.platform.jobs import Operations
from atbots.platform.store import StoreError
from atbots.platform.supervision_service import private_state, stop_private

PACKAGES = {"atmem": ">=2.3.10,<3", "atsys": ">=0.3.0b4,<0.4", "atflows": ">=0,<3"}


class Components:
    def __init__(self, store, prepare=None):
        self.store = store
        self.prepare = prepare
        self.lock = threading.Lock()
        self.state = {"status": "idle", "restart_required": False}

    def inspect(self, *, latest=False):
        rows = []
        for package in ("atbots", *PACKAGES):
            try:
                installed = version(package)
            except PackageNotFoundError:
                installed = None
            row = {"package": package, "installed": installed, "latest": None}
            if latest and package in PACKAGES:
                try:
                    with build_opener(ProxyHandler({}), NoRedirect()).open(
                        f"https://pypi.org/pypi/{package}/json", timeout=10
                    ) as response:
                        raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise ValueError("Oversized metadata")
                    row["latest"] = json.loads(raw)["info"]["version"]
                except (OSError, ValueError, KeyError):
                    row["check"] = "unavailable; retry later"
            rows.append(row)
        with self.lock:
            state = dict(self.state)
        return {
            "components": rows,
            "maintenance": state,
            "python": sys.executable,
            "scope": "Shared package versions; separate agent data and configuration",
            "upgrade_requires": "Pause agents, finish jobs and reconcile delegated work first. Close and reopen AtBots after upgrading. A package install does not start AtSys or AtFlows services.",
        }

    def upgrade(self, package, target, confirmed):
        if (
            package not in PACKAGES
            or not isinstance(target, str)
            or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}(?:(?:a|b|rc)[0-9]+)?", target)
            or confirmed is not True
        ):
            raise StoreError(
                "Select a component and an exact compatible version, then explicitly confirm the upgrade"
            )
        from packaging.specifiers import SpecifierSet

        if not SpecifierSet(PACKAGES[package]).contains(target, prereleases=True):
            raise StoreError(
                "Version is outside this AtBots build's compatibility range"
            )
        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name

        for distribution in distributions():
            for declaration in distribution.requires or []:
                requirement = Requirement(declaration)
                if (
                    canonicalize_name(requirement.name) == package
                    and (
                        requirement.marker is None
                        or requirement.marker.evaluate({"extra": ""})
                    )
                    and not requirement.specifier.contains(target, prereleases=True)
                ):
                    raise StoreError(
                        "This version conflicts with an installed package's compatibility pin; use a coordinated application upgrade"
                    )
        with self.lock:
            if self.state["status"] == "running" or self.state["restart_required"]:
                raise StoreError("Maintenance is active or a restart is required")
            if any(
                a.state == "active"
                for a in self.store.list()
                if a.name != "control-room"
            ):
                raise StoreError("Pause every agent before package maintenance")
            if any(
                j["status"] in {"running", "cancel_requested", "queued"}
                for j in Operations(self.store).list()
            ):
                raise StoreError(
                    "Finish or cancel queued/running jobs before maintenance"
                )
            links = Delegations(self.store).list()
            private = {
                a.name: state
                for a in self.store.list()
                if a.name != "control-room"
                and (state := private_state(self.store, a.name)) is not None
            }
            if len(links) > 20:
                raise StoreError(
                    "Use a dedicated maintenance environment for this many delegated tasks"
                )
            for link in links:
                try:
                    owned = private.get(link["agent"])
                    if owned and owned["endpoint"] == link["endpoint"]:
                        task = next(
                            (
                                t
                                for t in owned["tasks"]
                                if t["id"] == link["upstream_id"]
                            ),
                            None,
                        )
                        if task is None:
                            raise StoreError(
                                "Delegated task is missing from its private state"
                            )
                    else:
                        task = AtSysClient(link["endpoint"]).status(link["upstream_id"])
                except (OSError, ValueError, RuntimeError):
                    raise StoreError(
                        "Cannot verify delegated work is stopped. Restore its service or use a separate maintenance environment"
                    ) from None
                if task.get("status") not in {
                    "completed",
                    "stopped",
                    "needs_attention",
                }:
                    raise StoreError(
                        "Complete or stop delegated work through AtSys before component maintenance"
                    )
            self.state = {
                "id": uuid.uuid4().hex,
                "status": "running",
                "package": package,
                "target": target,
                "restart_required": False,
            }

        def perform():
            try:
                if self.prepare:
                    self.prepare()
                # No generated commands, extra index URLs, shell, or provider credentials.
                with FileLock(str(self.store.root / "runner.lock"), timeout=0):
                    for name in private:
                        stop_private(self.store, name, confirmed=True)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "--upgrade",
                            f"{package}=={target}",
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=300,
                        check=False,
                    )
                    checked = subprocess.run(
                        [sys.executable, "-m", "pip", "check"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=60,
                        check=False,
                    )
                with self.lock:
                    self.state.update(
                        status="installed"
                        if result.returncode == checked.returncode == 0
                        else "needs_attention",
                        restart_required=True,
                    )
            except Exception as error:  # noqa: BLE001 - package installers may echo private environment values
                with self.lock:
                    self.state.update(
                        status="needs_attention",
                        restart_required=True,
                        message=str(error)
                        if isinstance(error, StoreError)
                        else "Maintenance did not finish. Check service readiness and package compatibility; no automatic rollback was performed",
                    )

        threading.Thread(target=perform, daemon=True).start()
        return self.inspect()
