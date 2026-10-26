import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from pydantic_ai.models.test import TestModel

from atbots.platform.store import AgentStore
from atbots.platform.web import create_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    from atbots.platform.connections import Connections

    monkeypatch.setattr(
        "atbots.platform.connections.auth_status", lambda kind: {"state": "missing"}
    )

    async def models(self, connection):
        return ["qwen3:4b", "fixture-model"]

    monkeypatch.setattr(Connections, "_models", models)
    store = AgentStore(tmp_path)
    server, token = create_server(
        store,
        token="test-credential",
        model=TestModel(custom_output_text='{"action":"list"}'),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", token, store
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, path, data=None, **headers):
    url, token, _ = server
    headers = {"Authorization": f"Bearer {token}", **headers}
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(
        Request(
            url + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
        ),
        timeout=5,
    ) as response:
        return json.load(response)


def test_authenticated_approval_survives_reload(server):
    proposal = request(
        server, "/api/operation", {"action": "create", "name": "researcher"}
    )
    state = request(server, "/api/state")
    assert state["approvals"][0]["id"] == proposal["approval_required"]
    result = request(server, "/api/approve", {"id": proposal["approval_required"]})
    assert result["applied"]["name"] == "researcher"
    assert request(server, "/api/state")["approvals"] == []
    with pytest.raises(HTTPError) as error:
        request(server, "/api/approve", {"id": proposal["approval_required"]})
    assert error.value.code == 400


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Authorization": "Bearer wrong"}, 401),
        ({"Origin": "https://evil.example"}, 403),
        ({"Host": "evil.example"}, 403),
    ],
)
def test_web_rejects_untrusted_clients(server, headers, status):
    with pytest.raises(HTTPError) as error:
        request(server, "/api/state", **headers)
    assert error.value.code == status


def test_artifact_boundary_and_secret_filter(server):
    _, _, store = server
    store.create("researcher")
    (store.workspace("researcher") / "files" / "result.txt").write_text(
        "fixture result"
    )
    with urlopen(
        Request(
            server[0] + "/api/artifact?agent=researcher&path=result.txt",
            headers={"Authorization": f"Bearer {server[1]}"},
        )
    ) as response:
        assert response.read() == b"fixture result"
        assert response.headers["Cache-Control"] == "no-store"
    with pytest.raises(HTTPError):
        request(server, "/api/artifact?agent=researcher&path=../../registry.db")


def test_public_assets_and_authenticated_doctor(server):
    for asset, mime in (
        ("control-room.js", "text/javascript"),
        ("control-room.css", "text/css"),
    ):
        with urlopen(server[0] + "/" + asset) as response:
            assert response.headers["Content-Type"].startswith(mime)
            assert response.read()
            assert "unsafe-inline" not in response.headers["Content-Security-Policy"]
    with pytest.raises(HTTPError) as error:
        urlopen(server[0] + "/api/doctor")
    assert error.value.code == 401
    result = request(server, "/api/doctor")
    assert result["model_inference_tested"] is False
    assert result["cloud_permissions_tested"] is False


def test_selected_memory_and_job_data_never_leak_to_fleet_state(server):
    from atbots.platform.jobs import Operations
    from atbots.platform.memory import AtMemMemory

    store = server[2]
    for name in ("coder", "writer"):
        store.create(name)
    Operations(store).submit("coder", "private objective cobalt-canary")
    proposal = request(
        server,
        "/api/agent-memory",
        {"name": "coder", "action": "remember", "text": "I prefer cobalt notebooks"},
    )
    assert "cobalt" not in json.dumps(request(server, "/api/state"))
    assert "cobalt" not in json.dumps(request(server, "/api/state?agent=writer"))
    assert "cobalt" in json.dumps(request(server, "/api/state?agent=coder"))
    request(server, "/api/approve", {"id": proposal["approval_required"]})
    assert AtMemMemory(store, "coder").inspect()
    assert not AtMemMemory(store, "writer").inspect()


def test_setup_forms_reject_name_collisions_and_stale_settings(server):
    server[2].create("coder")
    data = {"name": "coder", "connection": "local", "model": "qwen3:4b"}
    with pytest.raises(HTTPError):
        request(server, "/api/setup/agent", data)
    with pytest.raises(HTTPError):
        request(
            server,
            "/api/setup/agent",
            {**data, "action": "configure", "expected_revision": 0},
        )
    result = request(
        server,
        "/api/setup/agent",
        {**data, "action": "configure", "expected_revision": 1, "state": "paused"},
    )
    request(server, "/api/approve", {"id": result["approval_required"]})
    assert server[2].get("coder").state == "paused"


def test_history_projection_is_scoped_and_never_displays_internal_thinking(server):
    from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart
    from pydantic_ai.models.function import FunctionModel

    from atbots.platform.session import AgentSession

    store = server[2]
    for name in ("coder", "writer"):
        store.create(name)

        def model(messages, info, name=name):
            return ModelResponse(
                parts=[
                    ThinkingPart("internal-only-fixture"),
                    TextPart(name + "-only-answer"),
                ]
            )

        AgentSession(store, name, model=FunctionModel(model), memory=None).chat(
            name + "-only-question"
        )
    value = request(server, "/api/conversation?agent=coder")
    assert value["messages"] == [
        {"speaker": "You", "text": "coder-only-question"},
        {"speaker": "coder", "text": "coder-only-answer"},
    ]
    assert "writer" not in json.dumps(value)
    assert "internal-only" not in json.dumps(value)
    assert "coder-only-answer" not in json.dumps(
        request(server, "/api/conversation?agent=control-room")
    )


def test_ui_first_connection_model_and_agent_journey(server, tmp_path, monkeypatch):
    from pathlib import Path

    from atbots.platform.connections import APIKeys

    secrets = {}
    private_setup = []

    def start_private(store, name, **kwargs):
        private_setup.append((name, kwargs))
        return {
            "endpoint": "http://127.0.0.1:4311",
            "next": "Private AtSys ready; save your chosen roles. No task started.",
        }

    monkeypatch.setattr(
        "atbots.platform.supervision_service.start_private", start_private
    )
    monkeypatch.setattr(APIKeys, "__init__", lambda self: None)
    monkeypatch.setattr(
        APIKeys, "save", lambda self, profile, value: secrets.update({profile: value})
    )
    monkeypatch.setattr(APIKeys, "load", lambda self, profile: secrets[profile])
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **(
                {"executable_path": str(chrome)}
                if chrome.exists()
                else {"channel": "chromium"}
            )
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server[0] + "#token=" + server[1])
        page.get_by_text("Connected ·", exact=False).wait_for()
        page.get_by_role("button", name="Setup & connections", exact=True).click()
        page.locator("#connect-provider").select_option("openai-compatible")
        page.locator("#connect-key").fill("fixture-not-a-real-api-key")
        page.get_by_role("button", name="Save API connection", exact=True).click()
        expect(page.locator("#setup-status")).to_contain_text(
            "saved in the OS keychain"
        )
        assert page.locator("#connect-key").input_value() == ""
        assert "fixture-not-a-real-api-key" not in page.content()
        assert "fixture-not-a-real-api-key" not in server[
            2
        ].database.read_bytes().decode(errors="ignore")
        page.locator("#setup-close").click()
        saved = next(
            row
            for row in request(server, "/api/connections")["connections"]
            if row["kind"] == "openai-compatible"
        )
        page.locator("#control-model").click()
        expect(page.locator("#agent-connection")).to_contain_text("OpenAI API")
        page.locator("#agent-connection").select_option(saved["id"])
        expect(page.locator("#model")).to_contain_text("fixture-model")
        page.locator("#model").select_option("fixture-model")
        page.locator("#remote").check()
        page.get_by_role("button", name="Review changes", exact=True).click()
        expect(page.locator("#agent-dialog")).not_to_be_visible()
        page.get_by_role("button", name="Approve", exact=True).click()
        expect(page.locator("#approvals")).to_be_empty()
        assert server[2].get("control-room").binding.kind == "openai-compatible"
        page.locator("#new-agent").click()
        page.locator("#agent-name").fill("coder")
        page.locator("#agent-connection").select_option(saved["id"])
        expect(page.locator("#model")).to_contain_text("fixture-model")
        page.locator("#model").select_option("fixture-model")
        page.locator("#remote").check()
        page.get_by_role("button", name="Review changes", exact=True).click()
        expect(page.locator("#agent-dialog")).not_to_be_visible()
        page.get_by_role("button", name="Approve", exact=True).click()
        expect(page.locator("#agents")).to_contain_text("coder · active")
        page.locator("#agents button").filter(has_text="coder").click()
        page.locator("#environment").click()
        expect(page.locator("#conversation")).to_contain_text(
            "Memory: AtMem · this agent only"
        )
        expect(page.locator("#conversation")).to_contain_text(
            str(server[2].workspace("coder") / "files")
        )
        page.locator("#supervision-settings").click()
        page.locator("#atsys-start-private").click()
        expect(page.locator("#atsys-endpoint")).to_have_value("http://127.0.0.1:4311")
        assert private_setup == [("coder", {"confirmed": True, "initialize_git": True})]
        page.locator("#atsys-worker").select_option("claude")
        page.locator("#atsys-supervisor").select_option("copilot")
        page.locator("#atsys-worker-model").fill("operator-chosen-model")
        page.locator("#atsys-validator").fill("python -m pytest")
        page.locator("#atsys-criteria").fill("Tests pass")
        page.locator("#atsys-trusted").check()
        page.get_by_role("button", name="Save supervision settings", exact=True).click()
        expect(page.locator("#supervision-dialog")).not_to_be_visible()
        environment = request(server, "/api/environment", {"name": "coder"})
        assert environment["atsys"]["configuration"]["model"] == "operator-chosen-model"
        assert environment["atsys"]["live_health"] == "not_checked"
        assert (
            environment["atsys"]["configuration"]["endpoint"] == "http://127.0.0.1:4311"
        )
        definition = server[2].get("coder")
        server[2].configure(
            "coder",
            expected_revision=definition.revision,
            binding={
                **definition.binding.model_dump(),
                "model": "unlisted-existing-model",
            },
        )
        page.reload()
        page.get_by_text("Connected ·", exact=False).wait_for()
        page.locator("#agents button").filter(has_text="coder").click()
        page.locator("#settings").click()
        expect(page.locator("#model")).to_have_value("unlisted-existing-model")
        page.locator("#dialog-cancel").click()
        from concurrent.futures import ThreadPoolExecutor

        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_ai.models.function import FunctionModel

        from atbots.platform.session import AgentSession

        server[2].create("writer")

        def seed_history(name):
            AgentSession(
                server[2],
                name,
                model=FunctionModel(
                    lambda messages, info: ModelResponse(
                        parts=[TextPart(name + " private response")]
                    )
                ),
                memory=None,
            ).chat(name + " private question")

        # Match the web server's per-request thread, not Playwright's active loop.
        with ThreadPoolExecutor(max_workers=1) as pool:
            for name in ("coder", "writer"):
                pool.submit(seed_history, name).result(timeout=10)
        page.reload()
        page.get_by_text("Connected ·", exact=False).wait_for()
        page.locator("#agents button").filter(has_text="coder").click()
        expect(page.locator("#conversation")).to_contain_text("coder private response")
        page.locator("#message").fill("coder private draft")
        page.locator("#agents button").filter(has_text="writer").click()
        expect(page.locator("#message")).to_have_value("")
        expect(page.locator("#conversation")).to_contain_text("writer private response")
        expect(page.locator("#conversation")).not_to_contain_text(
            "coder private response"
        )
        page.locator("#agents button").filter(has_text="coder").click()
        expect(page.locator("#message")).to_have_value("coder private draft")
        expect(page.locator("#conversation")).not_to_contain_text(
            "writer private response"
        )
        page.locator("#environment").click()
        page.locator("#components").click()
        expect(page.locator("#component-list")).to_contain_text("atmem:")
        page.locator("#component-close").click()
        page.screenshot(path=str(tmp_path / "journey-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(tmp_path / "journey-mobile.png"), full_page=True)
        assert errors == []
        print("Corrective journey screenshots:", tmp_path)
        browser.close()


def test_browser_settings_are_proposals_not_immediate_mutations(server):
    from pathlib import Path

    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **(
                {"executable_path": str(chrome)}
                if chrome.exists()
                else {"channel": "chromium"}
            )
        )
        page = browser.new_page()
        page.goto(server[0] + "#token=" + server[1])
        page.get_by_text("Connected ·", exact=False).wait_for()
        page.get_by_role("button", name="New agent", exact=True).click()
        page.locator("#agent-name").fill("writer")
        page.locator("#instructions").fill("Write concise reports.")
        page.get_by_role("button", name="Review changes", exact=True).click()
        expect(page.locator("#agent-dialog")).not_to_be_visible(timeout=20000)
        assert "writer" not in [a.name for a in server[2].list()]
        page.get_by_role("button", name="Approve", exact=True).click()
        expect(page.locator("#agents")).to_contain_text("writer · active")
        page.locator("#agents button").filter(has_text="writer").click()
        page.get_by_role("button", name="Settings", exact=True).click()
        page.locator("#instructions").fill("Prefer detailed reports.")
        page.get_by_role("button", name="Review changes", exact=True).click()
        expect(page.locator("#agent-dialog")).not_to_be_visible(timeout=20000)
        assert server[2].get("writer").instructions == "Write concise reports."
        page.get_by_role("button", name="Reject", exact=True).click()
        expect(page.locator("#approvals")).to_be_empty()
        assert server[2].get("writer").instructions == "Write concise reports."
        browser.close()


def test_real_browser_control_room_desktop_mobile(server, tmp_path):
    from pathlib import Path

    playwright_api = pytest.importorskip("playwright.sync_api")
    expect, sync_playwright = playwright_api.expect, playwright_api.sync_playwright

    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **(
                {"executable_path": str(chrome)}
                if chrome.exists()
                else {"channel": "chromium"}
            )
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(server[0] + "#token=" + server[1])
        page.get_by_text("Connected ·", exact=False).wait_for()
        assert page.get_by_role("heading", name="Work and outcomes").is_visible()
        page.get_by_role("textbox").fill("List my agents")
        page.get_by_role("button", name="Send", exact=True).click()
        expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
        expect(page.locator("#conversation")).to_contain_text("control-room · active")
        proposal = request(
            server, "/api/operation", {"action": "create", "name": "researcher"}
        )
        page.reload()
        page.get_by_role("button", name="Approve", exact=True).click()
        expect(page.locator("#conversation")).to_contain_text("Saved researcher")
        expect(page.locator("#agents")).to_contain_text("researcher · active")
        assert proposal["approval_required"] not in [
            item["id"] for item in request(server, "/api/state")["approvals"]
        ]
        from atbots.platform.memory import AtMemMemory

        store = server[2]
        AtMemMemory(store, "researcher").remember("I prefer concise technical answers")
        (store.workspace("researcher") / "files" / "report.txt").write_text(
            "Inspectable fixture report"
        )
        page.locator("#agents button").filter(has_text="researcher").click()
        page.get_by_role("button", name="Memory", exact=True).click()
        expect(page.locator("#conversation")).to_contain_text("concise technical")
        page.get_by_role("button", name="Files", exact=True).click()
        page.get_by_role("button", name="View report.txt", exact=True).click()
        expect(page.locator("#conversation")).to_contain_text(
            "Inspectable fixture report"
        )
        page.screenshot(path=str(tmp_path / "desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.get_by_role("button", name="Send", exact=True).is_visible()
        page.screenshot(path=str(tmp_path / "mobile.png"), full_page=True)
        print("UI screenshots:", tmp_path)
        browser.close()
