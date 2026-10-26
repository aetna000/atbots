"""First-party authenticated loopback client of the same management operations."""

import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit

from atbots.platform.control import ControlPlan, ControlRoom
from atbots.platform.integrations import Delegations
from atbots.platform.jobs import Operations
from atbots.platform.scheduler import Scheduler
from atbots.platform.store import stamp
from atbots.platform.tools import WorkspaceTools


def create_server(store, *, port=0, token=None, model=None):
    credential = token or secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # no prompts, tokens or private artifacts in access logs

        def respond(self, status, data, *, content_type="application/json"):
            raw = (
                data
                if isinstance(data, bytes)
                else json.dumps(data, ensure_ascii=False).encode()
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            hosts = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            if self.headers.get("Host") not in hosts:
                self.respond(403, {"error": "Loopback host required"})
                return False
            auth = self.headers.get("Authorization", "")
            if not hmac.compare_digest(auth, "Bearer " + credential):
                self.respond(
                    401,
                    {
                        "error": "Reconnect through the CLI-opened authenticated control-room URL"
                    },
                )
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers["Host"]:
                self.respond(403, {"error": "Same-origin request required"})
                return False
            return True

        def do_GET(self):
            if self.path == "/":
                return self.respond(
                    200,
                    files("atbots.platform").joinpath("control-room.html").read_bytes(),
                    content_type="text/html; charset=utf-8",
                )
            if not self.authorized():
                return
            try:
                parsed = urlsplit(self.path)
                if parsed.path == "/api/state":
                    return self.respond(
                        200,
                        {
                            "at": stamp(),
                            "agents": [a.model_dump(mode="json") for a in store.list()],
                            "jobs": Operations(store).list(),
                            "schedules": Scheduler(store).list(),
                            "approvals": Operations(store).pending_approvals(),
                            "delegations": Delegations(store).list(),
                        },
                    )
                if parsed.path == "/api/artifact":
                    query = parse_qs(parsed.query)
                    name, path = query["agent"][0], query["path"][0]
                    text = WorkspaceTools(
                        store.workspace(name) / "files", read=True
                    ).read_file(path)
                    return self.respond(
                        200, text.encode(), content_type="application/octet-stream"
                    )
                self.respond(404, {"error": "Unknown endpoint"})
            except Exception:  # noqa: BLE001 - private artifact/SDK errors must not leak into HTTP responses
                self.respond(
                    400,
                    {
                        "error": "Request refused; inspect target, scope and artifact permissions"
                    },
                )

        def do_POST(self):
            if not self.authorized():
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 64000:
                    raise ValueError()
                data = json.loads(self.rfile.read(length))
                room = ControlRoom(store, model=model)
                if self.path == "/api/chat" and set(data) == {"message"}:
                    result = room.dispatch(room.plan(data["message"]))
                elif self.path == "/api/operation":
                    result = room.dispatch(ControlPlan.model_validate(data))
                elif self.path == "/api/approve" and set(data) == {"id"}:
                    result = room.approve(data["id"])
                elif self.path == "/api/reject" and set(data) == {"id"}:
                    room.reject(data["id"])
                    result = {"speaker": "control-room", "rejected": True}
                elif self.path == "/api/agent" and set(data) == {"name", "message"}:
                    result = room.dispatch(
                        ControlPlan(
                            action="ask", name=data["name"], message=data["message"]
                        )
                    )
                else:
                    return self.respond(404, {"error": "Unknown operation"})
                self.respond(200, result)
            except Exception:  # noqa: BLE001 - preserve no-replay boundary and redact credentials
                self.respond(
                    400,
                    {
                        "error": "Operation could not be applied; check target, approval, configuration and execution receipts. No automatic replay."
                    },
                )

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server, credential


def serve(store, *, port=0, open_browser=True):
    import webbrowser

    server, token = create_server(store, port=port)
    address = f"http://127.0.0.1:{server.server_port}"
    print(f"AtBots control room: {address}")
    if open_browser:
        webbrowser.open(address + "#token=" + token)
    else:
        server.server_close()
        raise ValueError(
            "Headless web authentication provisioning is not configured; use the CLI-opened browser or an authenticated local API client"
        )
    try:
        server.serve_forever()
    finally:
        server.server_close()
