import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from atbots.platform.integrations import (
    AtSysClient,
    SupervisedObjective,
    atflows_binding,
)
from atbots.platform.models import ModelBinding


def test_native_subscription_not_proxy_and_explicit_trusted_execution():
    with pytest.raises(ValueError):
        atflows_binding(
            ModelBinding(kind="chatgpt", egress_class="remote"), "http://127.0.0.1:8080"
        )
    binding = atflows_binding(ModelBinding(), "http://127.0.0.1:8080/ollama")
    assert binding.kind == "openai-compatible" and binding.egress_class == "local"
    with pytest.raises(ValueError):
        SupervisedObjective(
            worker="claude",
            validation_argv=["python", "-m", "pytest"],
            success_criteria=["Tests pass"],
            stages=["Test"],
            plan="Run tests",
        )


def test_version_guard_and_native_task_payload(tmp_path):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"version": "0.3.0b4"}).encode())

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(data)
            self.send_response(201)
            self.end_headers()
            self.wfile.write(b'{"id":"task-fixture","status":"queued"}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    from atbots.platform.store import AgentStore

    store = AgentStore(tmp_path)
    definition = store.create("researcher")
    try:
        client = AtSysClient(f"http://127.0.0.1:{server.server_port}")
        contract = SupervisedObjective(
            validation_argv=["python", "-m", "pytest"],
            success_criteria=["Tests pass"],
            stages=["Inspect", "Test"],
            plan="Run scoped test suite",
        )
        assert (
            client.submit(
                definition,
                store.workspace("researcher") / "files",
                "Run the test suite",
                contract,
            )["id"]
            == "task-fixture"
        )
        assert requests[0]["goalContract"]["observers"][0]["signal"] == "validator"
        assert requests[0]["worker"] == "codex"
    finally:
        server.shutdown()
        server.server_close()
