import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from atbots.platform.browser import BrowserTools
from atbots.platform.models import Capabilities
from atbots.platform.skills import Skills
from atbots.platform.store import AgentStore
from atbots.platform.tools import WorkspaceTools


def test_file_grants_traversal_secret_filter_and_no_overwrite(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    tools = WorkspaceTools(root, read=True, create=True)
    tools.create_file("report.txt", "Fixture report")
    assert tools.read_file("report.txt") == "Fixture report"
    with pytest.raises(FileExistsError):
        tools.create_file("report.txt", "replace")
    with pytest.raises(PermissionError):
        tools.read_file("../outside")
    with pytest.raises(PermissionError):
        WorkspaceTools(root).create_file("a", "text")
    with pytest.raises(ValueError):
        tools.create_file("secret.txt", "password is fake-fixture")
    assert not (root / "secret.txt").exists()


def test_reviewed_skill_hash_and_code_approval(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("Use primary sources and cite evidence.")
    manager = Skills(tmp_path / "installed")
    review = manager.review(str(source))
    (source / "script.py").write_text("print('fixture')")
    with pytest.raises(ValueError, match="changed"):
        manager.install("research", str(source), review["sha256"])
    review = manager.review(str(source))
    with pytest.raises(PermissionError):
        manager.install("research", str(source), review["sha256"])
    assert not manager.install(
        "research", str(source), review["sha256"], allow_code=True
    )["code_auto_executed"]
    assert "primary" in manager.load_skill("research")


def test_browser_policy_and_real_chrome_fixture(tmp_path):
    pytest.importorskip("playwright")
    from pathlib import Path

    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        pytest.skip("Real browser fixture requires provisioned Chrome on this host")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b'<title>AtBots fixture</title><label>Topic<input aria-label="Topic"></label><button onclick="this.innerText=\'Saved\'">Save draft</button>'
            )

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    store = AgentStore(tmp_path / "platform")
    store.create("researcher")
    caps = Capabilities(
        browser_domains=["127.0.0.1"],
        browser_actions=["navigate", "snapshot", "type", "click", "screenshot"],
        vision=True,
    )

    async def run():
        async with BrowserTools(
            store.workspace("researcher") / "browser", caps
        ) as browser:
            assert not browser.allowed_url("https://x.com")
            with pytest.raises(PermissionError):
                await browser.browser_navigate("https://example.com")
            await browser.browser_navigate(f"http://127.0.0.1:{server.server_port}")
            await browser.browser_type("Topic", "Fixture topic")
            await browser.browser_click("button", "Save draft")
            assert "Saved" in await browser.browser_snapshot()
            screenshot = await browser.browser_screenshot()
            assert screenshot.content[0].media_type == "image/png"
            from cryptography.fernet import Fernet

            key = Fernet.generate_key()
            await browser.browser.add_cookies(
                [
                    {
                        "name": "fixture",
                        "value": "isolated-fixture-value",
                        "url": f"http://127.0.0.1:{server.server_port}",
                    }
                ]
            )
            payload = await browser.export_session(key)
            assert b"isolated-fixture-value" not in payload
            await browser.browser.clear_cookies()
            assert (await browser.import_session(payload, key))["restored"]

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
