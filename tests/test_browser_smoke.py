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
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"
ROLE_ROOT = Path(__file__).parent / "fixtures" / "roles_demo"
DISPATCH_ROOT = Path(__file__).parent / "fixtures" / "dispatch_demo"
INHERITANCE_ROOT = Path(__file__).parent / "fixtures" / "inheritance_demo"


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
        assert execute("return document.querySelectorAll('.module-node.is-main').length") == 1
        assert execute("return document.querySelectorAll('.module-api-chip').length") > 0
        assert execute("return document.querySelectorAll('.boundary-node').length") == 0
        assert execute("return document.querySelectorAll('.macro-edge').length") == 0
        assert execute("return window.__ARCHMAP_ERRORS__") == []
        execute("document.getElementById('relationModeBtn').click(); return true")
        assert execute("return document.getElementById('relationModeBtn').getAttribute('aria-pressed')") == "true"
        execute("document.getElementById('relationModeBtn').click(); return true")
        execute("document.querySelector('[data-expand]').click(); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.mini-node').length") > 0
        execute("location.hash='#/module/entry'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.main-flow-node').length") > 0
        assert execute("return document.querySelectorAll('.boundary-node').length") == 0
        assert execute("return document.querySelectorAll('.module-contracts.is-visible').length") == 1
        assert execute("return document.querySelectorAll('.contracts-track .module-api-chip').length") > 0
        execute("document.querySelector('[data-main-view=\"capabilities\"]').click(); return true")
        time.sleep(.3)
        assert execute("return document.querySelectorAll('.function-node').length") == 1
        execute("location.hash='#/module/entry/function/fn%3Aapp.main.main'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.method-page').length") == 1
        assert execute("return document.querySelectorAll('.method-source-line').length") > 0
        assert execute("return document.querySelectorAll('.method-call-item').length") > 0
        assert execute("return document.querySelectorAll('.flow-node').length") == 0
        assert execute("return document.querySelector('.method-source-line.is-call-site') !== null") is True
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # Phase 1 class layer: classes are component nodes on the module page;
        # methods are listed in the class detail instead of being flattened.
        class_bundle = build_architecture(CLASS_ROOT)
        class_html = browser_dir / "class-layer.html"
        class_html.write_text(render_html(class_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": class_html.resolve().as_uri()})
        time.sleep(.6)
        execute("location.hash='#/module/worker'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        execute("document.querySelector('[data-main-view=\"capabilities\"]').click(); return true")
        time.sleep(.3)
        assert execute("return document.querySelectorAll('.class-node').length") == 2
        assert execute("return document.querySelectorAll('.class-node.is-abstract').length") == 1
        assert execute("return document.querySelectorAll('.function-node').length") == 1
        execute("document.querySelector('.class-node[data-uid=\"cls:app.worker.EchoWorker\"]').click(); return true")
        time.sleep(.2)
        assert execute("return document.querySelectorAll('.class-usage').length") == 2
        assert execute("return document.querySelectorAll('.detail-api-row').length") >= 1
        execute("document.querySelector('.detail-api-row').click(); return true")
        time.sleep(.3)
        assert execute("return document.querySelectorAll('.method-page').length") == 1
        assert execute("return document.querySelectorAll('.method-source-line').length") > 0
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # P2.2: role composition is visible, config/model render as type cards,
        # and type fields are shown instead of serialization APIs.
        role_bundle = build_architecture(ROLE_ROOT)
        role_html = browser_dir / "provider-roles.html"
        role_html.write_text(render_html(role_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": role_html.resolve().as_uri()})
        time.sleep(.6)
        execute("location.hash='#/module/roles'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        execute("document.querySelector('[data-main-view=\"capabilities\"]').click(); return true")
        time.sleep(.3)
        assert execute("return document.querySelectorAll('.module-contracts .role-count-chip').length") >= 6
        assert execute("return document.querySelectorAll('.class-node.is-type-card').length") == 3
        assert execute("return document.querySelectorAll('.type-field-chip').length") > 0
        assert execute("return Array.from(document.querySelectorAll('.function-node')).some(el => el.dataset.uid.includes('_provider_role'))") is False
        execute("Array.from(document.querySelectorAll('.class-node')).find(el => el.dataset.uid.endsWith('AppConfig')).click(); return true")
        time.sleep(.2)
        assert execute("return document.querySelectorAll('.type-field-row').length") == 3
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # P2.4: dispatch candidates are visible as dashed low-confidence
        # composition edges, never as ordinary call edges.
        dispatch_bundle = build_architecture(DISPATCH_ROOT)
        dispatch_html = browser_dir / "dispatch-flow.html"
        dispatch_html.write_text(render_html(dispatch_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": dispatch_html.resolve().as_uri()})
        time.sleep(.6)
        execute("location.hash='#/module/main'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.flow-dispatch').length") == 1
        assert execute("return document.querySelectorAll('.graph-edge.kind-composition').length") == 2
        assert execute("return document.querySelectorAll('.graph-edge.kind-composition.is-low').length") == 2
        assert execute("return document.querySelectorAll('.boundary-node').length") == 0
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # P3: inheritance/implements and polymorphic dispatch are visible as
        # structural hierarchy data and low-confidence composition edges.
        inheritance_bundle = build_architecture(INHERITANCE_ROOT)
        inheritance_html = browser_dir / "inheritance-flow.html"
        inheritance_html.write_text(render_html(inheritance_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": inheritance_html.resolve().as_uri()})
        time.sleep(.6)
        execute("location.hash='#/module/main'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.flow-dispatch').length") == 2
        assert execute("return document.querySelectorAll('.graph-edge.kind-composition.is-low').length") == 3
        execute("document.querySelector('[data-main-view=\"capabilities\"]').click(); return true")
        time.sleep(.25)
        assert execute("return document.querySelectorAll('.main-flow-node').length") == 0
        execute("location.hash='#/module/impl'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        execute("document.querySelector('[data-main-view=\"capabilities\"]')?.click(); return true")
        time.sleep(.25)
        assert execute("return document.querySelectorAll('.class-node').length") == 4
        execute("document.querySelector('.class-node[data-uid=\"cls:app.impl.EchoWorker\"]').click(); return true")
        time.sleep(.2)
        assert execute("return document.querySelectorAll('.class-hierarchy .hierarchy-row').length") >= 2
        assert execute("return document.querySelectorAll('.detail-api-badge.is-inherited').length") >= 1
        assert execute("return window.__ARCHMAP_ERRORS__") == []
    finally:
        if session:
            try:
                request("DELETE", f"/session/{session}")
            except Exception:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
