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

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.render_manager import RenderManager

build_architecture = PipelineManager().build_architecture
render_html = RenderManager().render

ROOT = Path(__file__).parent / "fixtures" / "student_demo"
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"
ROLE_ROOT = Path(__file__).parent / "fixtures" / "roles_demo"
DISPATCH_ROOT = Path(__file__).parent / "fixtures" / "dispatch_demo"
INHERITANCE_ROOT = Path(__file__).parent / "fixtures" / "inheritance_demo"
P4_ROOT = Path(__file__).parent / "fixtures" / "p4_demo"
REPO_ROOT = Path(__file__).parent.parent


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
        assert execute("return document.querySelectorAll('.module-node.is-main').length") == 0
        assert execute("return document.querySelectorAll('.module-api-chip').length") > 0
        assert execute("return document.querySelectorAll('.boundary-node').length") == 0
        assert execute("return document.querySelectorAll('.macro-edge').length") == 0
        assert execute("return document.querySelectorAll('[data-expand]').length") == 0
        assert execute("return document.querySelectorAll('.module-mini').length") == 0
        assert execute("return document.querySelectorAll('[data-open-module]').length") == 3
        assert execute("return window.__ARCHMAP_ERRORS__") == []
        execute("document.getElementById('relationModeBtn').click(); return true")
        assert execute("return document.getElementById('relationModeBtn').getAttribute('aria-pressed')") == "true"
        execute("document.getElementById('relationModeBtn').click(); return true")
        assert execute("return document.querySelectorAll('#projectFlowEntry.is-visible').length") == 1
        assert execute("return document.querySelectorAll('[data-open-flow]').length") == 1
        execute("document.querySelector('[data-open-flow]').click(); return true")
        time.sleep(.4)
        assert execute("return window.location.hash.startsWith('#/flow')") is True
        assert execute("return document.querySelectorAll('.execution-node').length") > 0
        assert execute("return document.querySelectorAll('.execution-edge').length") > 0
        assert execute("return document.querySelectorAll('.exec-node-header').length") > 0
        assert execute("return document.querySelectorAll('.exec-port-item').length") > 0
        assert execute("return document.querySelectorAll('.exec-port-dot, .execution-node.kind-merge').length") == 0
        assert execute("return document.querySelectorAll('.execution-node.kind-provider, .execution-node.kind-action, .execution-node.kind-statement').length") == 0
        assert execute("return document.querySelectorAll('[data-main-view], .main-flow-node').length") == 0
        assert execute("return document.querySelectorAll('.module-contracts.is-visible, .function-node, .class-node').length") == 0
        execute("location.hash='#/flow/missing-flow'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.35)
        assert execute("return document.querySelectorAll('.execution-node').length") > 0
        assert execute("return window.location.hash !== '#/flow/missing-flow'") is True
        execute("location.hash='#/module/entry'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.function-node').length") == 1
        assert execute("return document.querySelectorAll('.execution-node').length") == 0
        assert execute("return document.querySelectorAll('.module-contracts.is-visible').length") == 1
        assert execute("return document.querySelectorAll('.contracts-track .module-api-chip').length") > 0
        assert execute("return document.querySelectorAll('.macro-edge').length") == 0
        assert execute("return document.querySelectorAll('#projectFlowEntry.is-visible, .flow-picker.is-visible').length") == 0
        assert execute("return document.querySelectorAll('[data-expand]').length") == 0
        assert execute("return document.querySelectorAll('.module-mini').length") == 0
        drag_result = execute("""return (() => {
          const node = document.querySelector('.function-node');
          const rect = node.getBoundingClientRect();
          const x = rect.left + 12;
          const y = rect.top + 12;
          node.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0, pointerId: 7, clientX: x, clientY: y}));
          node.dispatchEvent(new PointerEvent('pointermove', {bubbles: true, pointerId: 7, clientX: x + 2600, clientY: y + 1800}));
          node.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, pointerId: 7, clientX: x + 2600, clientY: y + 1800}));
          return {left: parseFloat(node.style.left), top: parseFloat(node.style.top)};
        })()""")
        assert drag_result["left"] > 2200
        assert drag_result["top"] > 1600 or drag_result["left"] > 2200
        drag_result = execute("""return (() => {
          const node = document.querySelector('.function-node');
          const rect = node.getBoundingClientRect();
          const x = rect.left + 12;
          const y = rect.top + 12;
          node.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0, pointerId: 8, clientX: x, clientY: y}));
          node.dispatchEvent(new PointerEvent('pointermove', {bubbles: true, pointerId: 8, clientX: x - 5000, clientY: y - 5000}));
          node.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, pointerId: 8, clientX: x - 5000, clientY: y - 5000}));
          return {left: parseFloat(node.style.left), top: parseFloat(node.style.top)};
        })()""")
        assert drag_result["left"] < 0
        assert drag_result["top"] < 0
        execute("document.getElementById('fitBtn').click(); return true")
        assert execute("""return (() => {
          const node = document.querySelector('.function-node').getBoundingClientRect();
          const viewportRect = document.getElementById('viewport').getBoundingClientRect();
          return node.right > viewportRect.left && node.left < viewportRect.right
            && node.bottom > viewportRect.top && node.top < viewportRect.bottom;
        })()""") is True
        execute("localStorage.removeItem('archmap-v3-layout-v1'); return true")
        assert execute("return window.__ARCHMAP_ERRORS__") == []
        execute("location.hash='#/module/entry/function/fn%3Aapp.main.main'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.4)
        assert execute("return document.querySelectorAll('.method-page').length") == 1
        assert execute("return document.querySelectorAll('.method-source-line').length") > 0
        assert execute("return document.querySelectorAll('.method-call-item').length") > 0
        assert execute("return document.querySelectorAll('.main-flow-node').length") == 0
        assert execute("return document.querySelector('.method-source-line.is-call-site') !== null") is True
        method_theme = execute("""return (() => {
          const page = document.querySelector('.method-page');
          return {
            dark: window.matchMedia('(prefers-color-scheme: dark)').matches,
            background: getComputedStyle(page).backgroundColor,
            token: getComputedStyle(document.documentElement).getPropertyValue('--method-bg').trim(),
          };
        })()""")
        expected_bg = "rgb(9, 13, 19)" if method_theme["dark"] else "rgb(248, 250, 252)"
        assert method_theme["background"] == expected_bg
        assert method_theme["token"] == ("#090d13" if method_theme["dark"] else "#f8fafc")
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # Context-manager providers retain protocol semantics on the main flow.
        student_config = REPO_ROOT / "examples" / "student_system.archmap.json"
        student_bundle = build_architecture(REPO_ROOT / "Projects" / "student_system", student_config)
        student_html = browser_dir / "student-system-flow.html"
        student_html.write_text(render_html(student_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": f"{student_html.resolve().as_uri()}#/flow"})
        time.sleep(.8)
        assert execute("return window.__ARCHMAP_ERRORS__") == []
        assert execute("return document.querySelectorAll('.execution-node').length") > 0
        assert execute("return document.querySelectorAll('.exec-edge-capsule').length") == 0
        execution_labels = execute("return Array.from(document.querySelectorAll('.execution-node .exec-node-label')).map(node => node.textContent)")
        assert "server()" in execution_labels
        assert "client()" in execution_labels
        assert "NetworkAdapter.init_connection()" in execution_labels
        assert "with Spinner(message: str='加载中')" not in execution_labels
        assert "with Database(password: str)" not in execution_labels
        assert "Database.actions(client_input: bytes)" not in execution_labels
        assert "MenuSystem.run()" not in execution_labels
        assert execute("return document.querySelectorAll('.exec-node-signature').length") == 0
        execution_notes = execute("return Array.from(document.querySelectorAll('.execution-node .exec-node-note')).map(node => node.textContent)")
        assert any("服务器端" in note for note in execution_notes)
        assert any("客户端" in note for note in execution_notes)
        clipped_execution_bodies = execute("""return Array.from(document.querySelectorAll('.execution-node:not(.is-junction) .exec-node-body'))
          .filter(body => body.scrollHeight > body.clientHeight + 1).length""")
        assert clipped_execution_bodies == 0
        drag_result = execute("""return (() => {
          const node = Array.from(document.querySelectorAll('.execution-node'))
            .find(item => item.querySelector('.exec-node-label')?.textContent === 'server()');
          if (!node) return null;
          const edge = Array.from(document.querySelectorAll('.execution-edge'))
            .find(path => path.dataset.from === node.dataset.uid);
          const beforeEdge = edge?.getAttribute('d') || '';
          const rect = node.getBoundingClientRect();
          const x = rect.left + 16;
          const y = rect.top + 16;
          node.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0, pointerId: 41, clientX: x, clientY: y}));
          node.dispatchEvent(new PointerEvent('pointermove', {bubbles: true, pointerId: 41, clientX: x + 70, clientY: y + 90}));
          node.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, pointerId: 41, clientX: x + 70, clientY: y + 90}));
          const stored = JSON.parse(localStorage.getItem('archmap-v3-layout-v1') || '{}');
          return {
            left: parseFloat(node.style.left),
            top: parseFloat(node.style.top),
            edgeChanged: beforeEdge !== (edge?.getAttribute('d') || ''),
            storedFlows: Object.keys(stored.executions || {}).length,
          };
        })()""")
        assert drag_result is not None
        assert drag_result["edgeChanged"] is True
        assert drag_result["storedFlows"] > 0
        execute("localStorage.removeItem('archmap-v3-layout-v1'); return true")
        # The self-build main flow is an execution-only page.  Capability and
        # call-overview projections must not share this canvas.
        self_config = REPO_ROOT / "examples" / "archmap_v3.archmap.json"
        self_bundle = build_architecture(REPO_ROOT, self_config)
        self_html = browser_dir / "self-flow.html"
        self_html.write_text(render_html(self_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": f"{self_html.resolve().as_uri()}#/flow"})
        time.sleep(.8)
        assert execute("return document.querySelectorAll('.execution-node').length") > 0
        assert execute("return document.querySelectorAll('.main-flow-node, .function-node, .class-node').length") == 0
        assert execute("return document.querySelectorAll('.module-contracts.is-visible').length") == 0
        clipped_exec_bodies = execute("""return Array.from(document.querySelectorAll('.execution-node .exec-node-body'))
          .filter(body => body.scrollHeight > body.clientHeight + 1).length""")
        assert clipped_exec_bodies == 0
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
        assert execute("return document.querySelectorAll('.module-contracts .role-count-chip').length") >= 6
        assert execute("return document.querySelectorAll('.class-node.is-type-card').length") == 3
        assert execute("return document.querySelectorAll('.type-field-chip').length") > 0
        assert execute("return Array.from(document.querySelectorAll('.function-node')).some(el => el.dataset.uid.includes('_provider_role'))") is False
        execute("Array.from(document.querySelectorAll('.class-node')).find(el => el.dataset.uid.endsWith('AppConfig')).click(); return true")
        time.sleep(.2)
        assert execute("return document.querySelectorAll('.type-field-row').length") == 3
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # Removed call-overview UI must not leak back into the flow page.
        dispatch_bundle = build_architecture(DISPATCH_ROOT)
        dispatch_html = browser_dir / "dispatch-flow.html"
        dispatch_html.write_text(render_html(dispatch_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": f"{dispatch_html.resolve().as_uri()}#/flow"})
        time.sleep(.6)
        assert execute("return document.querySelectorAll('.execution-node').length") > 0
        assert execute("return document.querySelectorAll('.main-flow-node, [data-main-view]').length") == 0
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # P3: inheritance/implements remain visible on the module capability page.
        inheritance_bundle = build_architecture(INHERITANCE_ROOT)
        inheritance_html = browser_dir / "inheritance-flow.html"
        inheritance_html.write_text(render_html(inheritance_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": f"{inheritance_html.resolve().as_uri()}#/module/impl"})
        time.sleep(.6)
        assert execute("return document.querySelectorAll('.class-node').length") == 4
        execute("document.querySelector('.class-node[data-uid=\"cls:app.impl.EchoWorker\"]').click(); return true")
        time.sleep(.2)
        assert execute("return document.querySelectorAll('.class-hierarchy .hierarchy-row').length") >= 2
        assert execute("return document.querySelectorAll('.detail-api-badge.is-inherited').length") >= 1
        assert execute("return window.__ARCHMAP_ERRORS__") == []

        # P4: user surfaces and structural relations are visible without
        # introducing a class-focus page or statement-level flow.
        p4_bundle = build_architecture(P4_ROOT)
        p4_html = browser_dir / "p4-surfaces.html"
        p4_html.write_text(render_html(p4_bundle), encoding="utf-8")
        request("POST", f"/session/{session}/url", {"url": p4_html.resolve().as_uri()})
        time.sleep(.6)
        execute("location.hash='#/module/main'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.35)
        assert execute("return document.querySelectorAll('.user-surface-chip').length") >= 2
        execute("location.hash='#/module/service'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.35)
        assert execute("return document.querySelectorAll('.type-relation-chip.kind-composes').length") >= 1
        execute("document.querySelector('.class-node[data-uid=\"cls:app.manager.OrderManager\"]').click(); return true")
        time.sleep(.2)
        assert execute("return document.querySelectorAll('.structural-relation-row').length") >= 3
        execute("location.hash='#/module/main/function/fn%3Aapp.main.run_cli'; window.dispatchEvent(new HashChangeEvent('hashchange')); return true")
        time.sleep(.3)
        assert execute("return document.querySelectorAll('.method-page').length") == 1
        assert execute("return Array.from(document.querySelectorAll('.method-badge')).some(el => el.textContent.includes('surface:'))") is True
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
