"""One private local UI/runner process per workspace. No idle model calls."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from urllib.request import ProxyHandler, Request, build_opener

from filelock import FileLock

from atbots.platform.integrations import NoRedirect
from atbots.platform.scheduler import Scheduler
from atbots.platform.store import AgentStore, StoreError, stamp


def _metadata(store):
    path = store.root / "desktop.json"
    if path.is_symlink():
        raise StoreError("Desktop state must not be a symlink")
    if not path.exists():
        return None
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise StoreError("Desktop state is not private; fix its file permissions")
    value = json.loads(path.read_text())
    port = value.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise StoreError("Invalid local desktop state")
    return value


def _live(store):
    value = _metadata(store)
    if value is None:
        return None
    # Never send credentials to an address supplied by a state file or a redirect.
    address = f"http://127.0.0.1:{value['port']}"
    request = Request(
        address + "/api/desktop", headers={"Authorization": "Bearer " + value["token"]}
    )
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(
            request, timeout=1
        ) as response:
            status = json.load(response)
        if status.get("instance") == value["instance"]:
            return value
    except (OSError, ValueError):
        return None
    return None


def open_desktop(store, *, port=0):
    """Start or reopen this root's UI. Closing the tab/terminal does not stop work."""
    with FileLock(str(store.root / "desktop-start.lock"), timeout=15):
        value = _live(store)
        if value is None:
            # Refuse symlinks instead of following them while opening the log.
            log = store.root / "desktop.log"
            descriptor = os.open(
                log,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "ab") as output:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "atbots.platform.desktop",
                        "--root",
                        str(store.root),
                        "--port",
                        str(port),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=output,
                    start_new_session=os.name != "nt",
                    creationflags=(
                        subprocess.DETACHED_PROCESS
                        | subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                    if os.name == "nt"
                    else 0,
                )
            for _ in range(100):
                value = _live(store)
                if value:
                    break
                if process.poll() is not None:
                    raise StoreError(
                        "Desktop could not start. Check the private desktop.log in your AtBots root"
                    )
                time.sleep(0.1)
            else:
                raise StoreError(
                    "Desktop startup is pending. Reopen AtBots to check it; no duplicate restart was requested"
                )
    address = f"http://127.0.0.1:{value['port']}"
    if not webbrowser.open(address + "#token=" + value["token"]):
        raise StoreError(
            "Desktop is running but the browser could not open. Configure a local default browser and reopen AtBots"
        )
    print(
        f"AtBots: {address}\nLocal schedules stay available while this app and PC are running. No model is called while idle."
    )
    return address


def run(store, *, port=0):
    from atbots.platform.web import create_server

    with FileLock(str(store.root / "desktop-owner.lock"), timeout=0):
        status = {
            "instance": secrets.token_hex(16),
            "scheduler": "starting",
            "updated": stamp(),
        }
        stop = threading.Event()

        def prepare_maintenance():
            stop.set()
            thread.join(timeout=10)
            if thread.is_alive():
                raise StoreError("Runner has not stopped for maintenance")
            status.update(scheduler="maintenance", updated=stamp())

        server, token = create_server(
            store,
            port=port,
            desktop_status=status,
            prepare_maintenance=prepare_maintenance,
        )
        value = {
            "pid": os.getpid(),
            "port": server.server_port,
            "token": token,
            "instance": status["instance"],
        }
        destination = store.root / "desktop.json"
        temporary = store.root / ("desktop-" + status["instance"] + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream)
        os.replace(temporary, destination)

        def heartbeat():
            status.update(scheduler="ready", updated=stamp())

        def runner():
            for attempt in range(3):
                try:
                    Scheduler(store).serve(stop=stop, report=heartbeat)
                    return
                except Exception:  # noqa: BLE001 - never log private job/provider payloads
                    status.update(
                        scheduler="recovering",
                        updated=stamp(),
                        next="Retrying the scheduler, not replaying uncertain jobs",
                    )
                    if stop.wait(2**attempt):
                        return
            status.update(
                scheduler="blocked",
                updated=stamp(),
                next="Check setup and whether another runner owns this workspace; three runner retries exhausted, no uncertain job replay",
            )

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        try:
            server.serve_forever()
        finally:
            stop.set()
            thread.join(timeout=5)
            server.server_close()
            if (
                destination.exists()
                and _metadata(store)["instance"] == value["instance"]
            ):
                destination.unlink()
        return status.get("restart_requested", False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port", type=int, default=0)
    arguments = parser.parse_args()
    root = AgentStore(arguments.root)
    if run(root, port=arguments.port):
        open_desktop(root)
