from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from archmap.pipeline import build_architecture
from archmap.render import render_html

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.skipif(os.environ.get("ARCHMAP_RUN_BROWSER") != "1", reason="set ARCHMAP_RUN_BROWSER=1 to run WebDriver smoke test")
def test_browser_smoke() -> None:
    geckodriver = shutil.which("geckodriver")
    firefox = shutil.which("firefox")
    if not geckodriver or not firefox:
        pytest.skip("geckodriver/firefox not available")

    bundle = build_architecture(ROOT)
    browser_dir = Path.cwd() / ".archmap" / "browser-smoke"
    browser_dir.mkdir(parents=True, exist_ok=True)
    html_path = browser_dir / "architecture.html"
    html_path.write_text(render_html(bundle), encoding="utf-8")
    port = _free_port()
    proc = subprocess.Popen(
        [geckodriver, "--port", str(port), "--log", "error"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"

    def request(method: str, path: str, data: dict | None = None) -> dict:
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(
            base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read())

    session = None
    try:
        for _ in range(50):
            try:
                request("GET", "/status")
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(.1)
        else:
            pytest.fail("geckodriver did not start")
        session = request(
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "firefox",
                        "moz:firefoxOptions": {"args": ["-headless"]},
                    }
                }
            },
        )["value"]["sessionId"]

        def execute(script: str):
            return request(
                "POST",
                f"/session/{session}/execute/sync",
                {"script": script, "args": []},
            )["value"]

        request("POST", f"/session/{session}/url", {"url": html_path.resolve().as_uri()})
        time.sleep(.6)
        assert execute("return document.querySelectorAll('.module-node').length") == 3
        assert execute("return window.__ARCHMAP_ERRORS__") == []
        execute("document.querySelector('[data-expand]').click(); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.mini-node').length") > 0
        execute("location.hash='#/module/entry'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.function-node').length") == 1
        execute("location.hash='#/module/entry/function/fn%3Aapp.main.main'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.flow-node').length") > 2
        assert execute("return window.__ARCHMAP_ERRORS__") == []
    finally:
        if session:
            try:
                request("DELETE", f"/session/{session}")
            except Exception:
                pass
        proc.terminate()
        proc.wait(timeout=5)
