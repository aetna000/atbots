import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from pydantic_ai.models.test import TestModel

from atbots.platform.store import AgentStore
from atbots.platform.web import create_server


@pytest.fixture
def server(tmp_path):
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


def test_real_browser_control_room_desktop_mobile(server, tmp_path):
    from pathlib import Path

    playwright_api = pytest.importorskip("playwright.sync_api")
    expect, sync_playwright = playwright_api.expect, playwright_api.sync_playwright

    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **({"executable_path": str(chrome)} if chrome.exists() else {})
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(server[0] + "#token=" + server[1])
        page.get_by_text("Connected ·", exact=False).wait_for()
        assert page.get_by_role("heading", name="Work and outcomes").is_visible()
        page.get_by_role("textbox").fill("List my agents")
        page.get_by_role("button", name="Send", exact=True).click()
        expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
        expect(page.locator("#conversation")).to_contain_text("control-room · active")
        page.screenshot(path=str(tmp_path / "desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.get_by_role("button", name="Send", exact=True).is_visible()
        page.screenshot(path=str(tmp_path / "mobile.png"), full_page=True)
        print("UI screenshots:", tmp_path)
        browser.close()
