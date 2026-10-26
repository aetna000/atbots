"""First-party authenticated loopback client of the same management operations."""

import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit

from atbots.platform.connections import Connections, SignIns
from atbots.platform.control import ControlPlan, ControlRoom
from atbots.platform.integrations import Delegations
from atbots.platform.jobs import Operations
from atbots.platform.scheduler import Scheduler
from atbots.platform.store import StoreError, stamp
from atbots.platform.tools import WorkspaceTools


def create_server(
    store,
    *,
    port=0,
    token=None,
    model=None,
    desktop_status=None,
    prepare_maintenance=None,
):
    from atbots.platform.components import Components

    components = Components(store, prepare=prepare_maintenance)
    credential = token or secrets.token_urlsafe(32)
    ControlRoom(store, model=model)  # Create local control-room metadata; no inference.
    connections = Connections(store)
    sign_ins = SignIns(connections)

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
                "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'",
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
            assets = {
                "/control-room.js": "text/javascript; charset=utf-8",
                "/control-room.css": "text/css; charset=utf-8",
            }
            if self.path in assets:
                return self.respond(
                    200,
                    files("atbots.platform").joinpath(self.path[1:]).read_bytes(),
                    content_type=assets[self.path],
                )
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
                if parsed.path == "/api/desktop":
                    return self.respond(
                        200,
                        desktop_status
                        or {"scheduler": "not_started", "updated": stamp()},
                    )
                if parsed.path == "/api/components":
                    return self.respond(
                        200,
                        components.inspect(
                            latest=parse_qs(parsed.query).get("latest") == ["1"]
                        ),
                    )
                if parsed.path == "/api/conversation":
                    from pydantic_ai.messages import (
                        ModelMessagesTypeAdapter,
                        TextPart,
                        UserPromptPart,
                    )

                    name = parse_qs(parsed.query)["agent"][0]
                    revision, raw = store.history(name)
                    rows = []
                    for message in ModelMessagesTypeAdapter.validate_json(raw):
                        for part in message.parts:
                            if isinstance(part, UserPromptPart):
                                text = (
                                    part.content
                                    if isinstance(part.content, str)
                                    else "\n".join(
                                        value
                                        for value in part.content
                                        if isinstance(value, str)
                                    )
                                )
                                if name == "control-room":
                                    try:
                                        text = json.loads(text)["user_request"]
                                    except (ValueError, KeyError, TypeError):
                                        continue
                                rows.append({"speaker": "You", "text": text})
                            elif isinstance(part, TextPart):
                                text = part.content
                                if name == "control-room":
                                    try:
                                        text = (
                                            "Suggested operation: "
                                            + json.loads(text)["action"]
                                            + ". Check approvals and recorded outcomes to see what was actually applied."
                                        )
                                    except (ValueError, KeyError, TypeError):
                                        continue
                                rows.append({"speaker": name, "text": text})
                    return self.respond(
                        200,
                        {
                            "agent": name,
                            "revision": revision,
                            "messages": rows[-200:],
                            "earlier_messages": max(0, len(rows) - 200),
                        },
                    )
                if parsed.path == "/api/connections":
                    return self.respond(200, {"connections": connections.list()})
                if parsed.path == "/api/connection-models":
                    return self.respond(
                        200, connections.models(parse_qs(parsed.query)["id"][0])
                    )
                if parsed.path == "/api/sign-in":
                    return self.respond(
                        200, sign_ins.get(parse_qs(parsed.query)["id"][0])
                    )
                if parsed.path == "/api/doctor":
                    from atbots.platform.doctor import doctor

                    return self.respond(200, doctor(store))
                if parsed.path == "/api/state":
                    scope = parse_qs(parsed.query).get("agent", [None])[0]
                    if scope is not None:
                        store.get(scope)
                    jobs = Operations(store).list(scope)
                    if scope is None:
                        jobs = [
                            {
                                k: v
                                for k, v in j.items()
                                if k
                                in {
                                    "id",
                                    "agent",
                                    "status",
                                    "created",
                                    "updated",
                                    "stale",
                                }
                            }
                            for j in jobs
                        ]
                    approvals = Operations(store).pending_approvals()
                    approvals = [
                        p
                        for p in approvals
                        if not p["proposal"]["action"].startswith("memory_")
                        or p["proposal"]["name"] == scope
                    ]
                    return self.respond(
                        200,
                        {
                            "at": stamp(),
                            "desktop": desktop_status or {"scheduler": "not_started"},
                            "agents": [a.model_dump(mode="json") for a in store.list()],
                            "jobs": jobs,
                            "schedules": Scheduler(store).list(),
                            "approvals": approvals,
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
                if parsed.path == "/api/artifacts":
                    name = parse_qs(parsed.query)["agent"][0]
                    return self.respond(
                        200,
                        {
                            "agent": name,
                            "files": WorkspaceTools(
                                store.workspace(name) / "files", read=True
                            ).list_files(),
                        },
                    )
                self.respond(404, {"error": "Unknown endpoint"})
            except Exception as exc:  # noqa: BLE001 - private artifact/SDK errors must not leak into HTTP responses
                from atbots.auth import AuthError

                self.respond(
                    400,
                    {
                        "error": str(exc)
                        if isinstance(exc, (AuthError, StoreError))
                        else "Request refused; inspect target, scope and artifact permissions"
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
                if self.path == "/api/components/upgrade" and set(data) == {
                    "package",
                    "target",
                    "confirmed",
                }:
                    return self.respond(
                        200,
                        components.upgrade(
                            data["package"], data["target"], data["confirmed"]
                        ),
                    )
                if self.path == "/api/desktop/restart" and data == {"confirmed": True}:
                    if components.inspect()["maintenance"]["status"] == "running":
                        raise StoreError(
                            "Wait for package maintenance to finish before restarting"
                        )
                    if desktop_status is None:
                        raise ValueError("No managed desktop")
                    if any(
                        a.state == "active"
                        for a in store.list()
                        if a.name != "control-room"
                    ) or any(
                        j["status"] in {"running", "cancel_requested", "queued"}
                        for j in Operations(store).list()
                    ):
                        raise StoreError(
                            "Pause agents and finish/cancel jobs before restarting the app"
                        )
                    import threading

                    desktop_status["restart_requested"] = True
                    self.respond(
                        200,
                        {
                            "answer": "Restarting the local app. A fresh authenticated browser tab will open; agent data is retained."
                        },
                    )
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                maintenance = components.inspect()["maintenance"]
                if (
                    maintenance["status"] == "running"
                    or maintenance["restart_required"]
                ):
                    raise StoreError(
                        "Package maintenance requires restarting AtBots before further changes or model work"
                    )
                if self.path == "/api/setup/key" and set(data) == {
                    "provider",
                    "label",
                    "api_key",
                }:
                    return self.respond(
                        200,
                        {
                            "connection": connections.save_api(
                                data["provider"], data["label"], data["api_key"]
                            )
                        },
                    )
                if self.path == "/api/setup/login" and set(data) <= {
                    "provider",
                    "client_id",
                }:
                    return self.respond(
                        200, sign_ins.start(data["provider"], data.get("client_id"))
                    )
                if self.path == "/api/setup/atsys" and set(data) <= {
                    "name",
                    "confirmed",
                    "initialize_git",
                }:
                    from atbots.platform.supervision_service import start_private

                    return self.respond(
                        200,
                        start_private(
                            store,
                            data["name"],
                            confirmed=data["confirmed"],
                            initialize_git=data.get("initialize_git", False),
                        ),
                    )
                if self.path == "/api/setup/atsys-stop" and set(data) == {
                    "name",
                    "confirmed",
                }:
                    from atbots.platform.supervision_service import stop_private

                    return self.respond(
                        200,
                        stop_private(store, data["name"], confirmed=data["confirmed"]),
                    )
                if self.path == "/api/setup/supervision" and set(data) == {
                    "name",
                    "profile",
                }:
                    from atbots.platform.environment import configure_supervision

                    return self.respond(
                        200, configure_supervision(store, data["name"], data["profile"])
                    )
                if self.path == "/api/setup/supervision" and set(data) == {
                    "name",
                    "endpoint",
                    "worker",
                    "supervisor",
                    "worker_model",
                    "supervisor_model",
                    "validation_command",
                    "success_criteria",
                    "trusted_local_execution",
                }:
                    import shlex

                    from atbots.platform.environment import configure_supervision

                    profile = {
                        "endpoint": data["endpoint"],
                        "worker": data["worker"],
                        "supervisor_provider": data["supervisor"],
                        "model": data["worker_model"],
                        "supervisor_model": data["supervisor_model"],
                        "repair_provider": data["worker"],
                        "validation_argv": shlex.split(data["validation_command"]),
                        "success_criteria": data["success_criteria"],
                        "trusted_local_execution": data["trusted_local_execution"],
                        "stages": ["Implement", "Validate"],
                        "plan": "Complete the operator-approved objective inside this agent's workspace and run the declared independent acceptance command. Stop and report blockers rather than changing scope.",
                    }
                    return self.respond(
                        200, configure_supervision(store, data["name"], profile)
                    )
                room = ControlRoom(store, model=model)
                if self.path == "/api/setup/agent" and set(data) <= {
                    "name",
                    "connection",
                    "model",
                    "remote_allowed",
                    "file_read",
                    "file_create",
                    "instructions",
                    "state",
                    "capabilities",
                    "action",
                    "expected_revision",
                }:
                    from atbots.platform.models import Capabilities

                    name = data["name"]
                    existing = next((a for a in store.list() if a.name == name), None)
                    action = data.get("action", "create")
                    if action not in {"create", "configure"}:
                        raise StoreError("Unsupported setup operation")
                    if action == "create" and existing:
                        raise StoreError(
                            "Agent already exists; use Settings instead of creating over it"
                        )
                    if action == "configure" and (
                        existing is None
                        or data.get("expected_revision") != existing.revision
                    ):
                        raise StoreError(
                            "Agent configuration changed; reopen Settings before reviewing"
                        )
                    capabilities = (
                        existing.capabilities.model_dump()
                        if existing
                        else Capabilities().model_dump()
                    )
                    for key in ("file_read", "file_create"):
                        if key in data:
                            capabilities[key] = data[key]
                    capabilities.update(data.get("capabilities", {}))
                    result = room.dispatch(
                        ControlPlan(
                            action=action,
                            name=name,
                            binding=connections.binding(
                                data["connection"], data["model"]
                            ),
                            remote_allowed=data.get("remote_allowed", False),
                            instructions=data.get("instructions"),
                            state=data.get("state"),
                            capabilities=Capabilities.model_validate(capabilities),
                        )
                    )
                elif self.path == "/api/chat" and set(data) == {"message"}:
                    result = room.dispatch(room.plan(data["message"]))
                elif self.path == "/api/operation":
                    result = room.dispatch(ControlPlan.model_validate(data))
                elif self.path == "/api/agent-memory" and set(data) <= {
                    "name",
                    "action",
                    "text",
                    "record_id",
                }:
                    from atbots.platform.memory import AtMemMemory

                    name = data["name"]
                    if name == "control-room":
                        raise ValueError(
                            "Control room has fleet metadata, not private memory"
                        )
                    memory = AtMemMemory(store, name)
                    if data["action"] == "inspect":
                        result = {
                            "speaker": name,
                            "memories": memory.inspect(data.get("record_id")),
                        }
                    elif data["action"] == "search":
                        context = memory.context(data["text"], egress="local")
                        result = {
                            "speaker": name,
                            "answer": context.text,
                            "receipt": memory.confirm(context, "operator-agent-view"),
                        }
                    elif data["action"] == "remember":
                        from atbots.platform.environment import AgentEnvironment

                        result = AgentEnvironment(store, name, memory).request_remember(
                            data["text"]
                        )
                    elif data["action"] in {"correct", "forget"}:
                        from atbots.platform.environment import AgentEnvironment

                        result = AgentEnvironment(
                            store, name, memory
                        ).request_memory_change(
                            data["action"], data["record_id"], data.get("text")
                        )
                    else:
                        raise ValueError("Unknown agent-memory operation")
                elif self.path == "/api/environment" and set(data) == {"name"}:
                    from atbots.platform.environment import AgentEnvironment
                    from atbots.platform.memory import AtMemMemory

                    name = data["name"]
                    result = AgentEnvironment(
                        store,
                        name,
                        AtMemMemory(store, name) if name != "control-room" else None,
                    ).inspect_environment()
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
            except Exception as exc:  # noqa: BLE001 - preserve no-replay boundary and redact credentials
                from atbots.auth import AuthError
                from atbots.platform.session import SessionError

                if isinstance(exc, SessionError):
                    return self.respond(
                        400,
                        {
                            "error": "The model request failed or timed out. Open Settings to choose another connected model, or Check setup to inspect the environment. No task or tool sequence was automatically replayed."
                        },
                    )

                self.respond(
                    400,
                    {
                        "error": str(exc)
                        if isinstance(exc, (AuthError, StoreError))
                        else "Operation could not be applied; check target, approval, configuration and execution receipts. No automatic replay."
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
