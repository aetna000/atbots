"""Start an operator-requested private upstream AtSys, never the global service."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time

from filelock import FileLock

from atbots.platform.integrations import AtSysClient, loopback_url
from atbots.platform.store import StoreError

SUPERVISION_SUPPORTED = os.name == "posix"


def _alive(pid):
    if type(pid) is not int or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def start_private(store, name, *, confirmed, initialize_git=False):
    if confirmed is not True:
        raise StoreError("Confirm starting this agent's private local AtSys processes")
    if type(initialize_git) is not bool:
        raise StoreError("Git initialization must be an explicit checkbox choice")
    if not SUPERVISION_SUPPORTED:
        raise StoreError(
            "AtSys native supervision needs macOS/Linux. Windows task/workspace execution is not supported by this integration"
        )
    if name == "control-room":
        raise StoreError("Select an ordinary agent for private supervision")
    root = store.workspace(name) / "atsys-state"
    if root.is_symlink():
        raise StoreError("Private supervision state must not be a symlink")
    root.mkdir(mode=0o700, exist_ok=True)
    workspace = store.workspace(name) / "files"
    git = workspace / ".git"
    if git.is_symlink():
        raise StoreError("Workspace Git identity must not be a symlink")
    if initialize_git is True and not git.exists():
        git_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        git_env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        try:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "init.templateDir=",
                    "-c",
                    "init.defaultBranch=main",
                    "init",
                    "--quiet",
                    "--",
                    str(workspace),
                ],
                env=git_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            raise StoreError(
                "Workspace Git initialization failed. Install Git and retry; existing workspace files were not replaced"
            ) from None
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment["ATSYS_DATA_DIR"] = str(root.resolve())
    environment.pop("ATSYS_PORT", None)
    with FileLock(str(root / "atbots-setup.lock"), timeout=0):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "atsys", "ui", "--no-open"],
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if result.returncode:
                raise RuntimeError("AtSys dashboard startup failed")
            endpoint = loopback_url(result.stdout.strip())
            client = AtSysClient(endpoint)
            expected = hashlib.sha256(str(root.resolve()).encode()).hexdigest()
            if client.health().get("instanceId") != expected:
                raise RuntimeError("AtSys instance identity does not match this agent")
            result = subprocess.run(
                [sys.executable, "-m", "atsys", "service", "start"],
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode:
                raise RuntimeError("Private watchdog startup failed")
            deadline = time.monotonic() + 15
            retried = False
            while time.monotonic() < deadline:
                state = client.request("/api/operations")
                if (
                    state.get("daemonHealthy")
                    and (state.get("daemon") or {}).get("providerProtocol") == 1
                    and _alive((state.get("daemon") or {}).get("pid"))
                ):
                    return {
                        "agent": name,
                        "status": "ready",
                        "endpoint": endpoint,
                        "state_directory": str(root),
                        "task_started": False,
                        "next": "Save this endpoint with your chosen roles and acceptance command. No task has started.",
                    }
                # A stopped owner's heartbeat can remain fresh for ten seconds.
                if not retried and time.monotonic() > deadline - 4:
                    subprocess.run(
                        [sys.executable, "-m", "atsys", "service", "start"],
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=True,
                    )
                    retried = True
                time.sleep(0.25)
            raise RuntimeError("Private watchdog readiness was not confirmed")
        except Exception:  # noqa: BLE001 - native launch errors may contain private environment values
            raise StoreError(
                "Private AtSys setup needs attention. Check this agent's atsys-state/dashboard.log and installed AtSys version. No global service was restarted and no task was submitted"
            ) from None


def _owned_pid(pid, root, *, dashboard):
    """Verify exact package, UID and private instance before signalling a PID."""
    from importlib.resources import files

    if not _alive(pid) or pid == os.getpid():
        return False
    expected = str(
        (
            files("atsys") / "_runtime" / ("index.mjs" if dashboard else "daemon.mjs")
        ).resolve()
    )
    process = subprocess.run(
        ["ps", "-p", str(pid), "-o", "uid=,command="],
        capture_output=True,
        text=True,
        timeout=3,
        check=True,
    ).stdout.strip()
    uid, command = process.split(None, 1)
    if uid != str(os.getuid()) or expected not in command:
        raise StoreError(
            "Refusing to signal a process not owned by this private AtSys runtime"
        )
    if dashboard:
        if sys.platform == "darwin":
            output = subprocess.run(
                ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            ).stdout
            matches = str(root) in [
                line[1:] for line in output.splitlines() if line.startswith("n")
            ]
        else:
            matches = type(root)(f"/proc/{pid}/cwd").resolve() == root
        if not matches:
            raise StoreError(
                "Private AtSys process directory does not match this agent"
            )
    elif not command.endswith(" " + str(root)):
        raise StoreError("Private watchdog process does not match this agent")
    return True


def private_state(store, name):
    """Read owned state via the upstream CLI, including when its UI is stopped."""
    root = store.workspace(name) / "atsys-state"
    record = root / "dashboard.json"
    if not record.exists():
        return None
    if not SUPERVISION_SUPPORTED or root.is_symlink() or record.is_symlink():
        raise StoreError("Private supervision identity is unavailable on this host")
    value = json.loads(record.read_text())
    expected = hashlib.sha256(str(root.resolve()).encode()).hexdigest()
    port = value.get("port")
    if (
        value.get("instanceId") != expected
        or type(port) is not int
        or not 1024 <= port <= 65535
    ):
        raise StoreError("Invalid private AtSys identity")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment["ATSYS_DATA_DIR"] = str(root.resolve())
    environment.pop("ATSYS_PORT", None)

    def read(arguments):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "atsys", *arguments],
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            raise StoreError(
                "Private AtSys state could not be read; no work was restarted"
            ) from None
        if len(result.stdout) > 10_000_000:
            raise StoreError("Private AtSys state is too large for inline maintenance")
        return json.loads(result.stdout)

    service = read(["service", "status"])
    tasks = read(["task", "list", "--json"])
    if not isinstance(tasks, list):
        raise StoreError("Unrecognized private AtSys task listing")
    return {
        "root": root.resolve(),
        "record": value,
        "endpoint": f"http://127.0.0.1:{port}",
        "service": service.get("service", {}),
        "daemon": service.get("daemon"),
        "tasks": tasks,
    }


def private_report(store, name, task_id):
    """Read a durable report without starting the private service or a worker."""
    state = private_state(store, name)
    if state is None or not any(task.get("id") == task_id for task in state["tasks"]):
        raise StoreError("Task is not in this agent's private supervision state")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    environment["ATSYS_DATA_DIR"] = str(state["root"])
    environment.pop("ATSYS_PORT", None)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "atsys", "task", "report", task_id, "--json"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise StoreError(
            "Private AtSys report could not be read; no work was restarted"
        ) from None
    if len(result.stdout) > 10_000_000:
        raise StoreError("Private AtSys report is too large for inline inspection")
    return json.loads(result.stdout)


def stop_private(store, name, *, confirmed):
    """Stop only idle, identity-verified processes; keep all task data and reports."""
    if confirmed is not True or not SUPERVISION_SUPPORTED:
        raise StoreError("Confirm stopping this private AtSys on a supported host")
    root = store.workspace(name) / "atsys-state"
    if root.is_symlink() or (root / "dashboard.json").is_symlink():
        raise StoreError("Private supervision identity must not be a symlink")
    if not (root / "dashboard.json").exists():
        return {"agent": name, "status": "not_started", "data_retained": True}
    with FileLock(str(root / "atbots-setup.lock"), timeout=0):
        state = private_state(store, name)
        value = state["record"]
        if _alive(value.get("pid")):
            expected = hashlib.sha256(str(root.resolve()).encode()).hexdigest()
            if AtSysClient(state["endpoint"]).health().get("instanceId") != expected:
                raise StoreError("Refusing to stop another AtSys instance")
        if state["service"].get("loaded"):
            raise StoreError(
                "This private watchdog is OS-managed; use its native service manager before maintenance"
            )
        if any(
            t.get("status") not in {"completed", "stopped", "needs_attention"}
            or any(
                a.get("cleanupConfirmed") is False
                or a.get("status") in {"running", "scheduled", "paused"}
                for a in t.get("attempts", [])
            )
            for t in state["tasks"]
        ):
            raise StoreError(
                "Finish or stop private AtSys tasks before stopping their service"
            )
        targets = [
            (value.get("pid"), True),
            ((state.get("daemon") or {}).get("pid"), False),
        ]
        verified = [
            pid
            for pid, dashboard in targets
            if _owned_pid(pid, root.resolve(), dashboard=dashboard)
        ]
        for pid in verified:
            os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while any(_alive(pid) for pid in verified) and time.monotonic() < deadline:
            time.sleep(0.1)
        if any(_alive(pid) for pid in verified):
            raise StoreError(
                "Private shutdown is still pending; no forced kill or package upgrade was performed"
            )
        return {"agent": name, "status": "stopped", "data_retained": True}
