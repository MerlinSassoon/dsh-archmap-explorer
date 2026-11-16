from __future__ import annotations

import json
import re
from pathlib import Path

from archmap.pipeline import build_architecture
from archmap.render import render_html

ROOT = Path(__file__).parent / "fixtures" / "student_demo"
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"


def test_render_is_self_contained_and_embeds_real_data() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "@import" not in html
    assert "window.__ARCHMAP_DATA__" in html
    assert "fn:app.main.main" in html
    assert "student_demo" in html
    assert len(html) > 50000


def test_render_includes_annotations() -> None:
    bundle = build_architecture(ROOT)
    annotations = {
        "version": 1,
        "nodes": {
            "fn:app.main.main": {
                "summary": "程序入口",
                "details": "加载并处理学生数据",
                "sourceHash": bundle["functionDetails"][0]["sourceHash"],
            }
        },
    }
    html = render_html(bundle, annotations)
    assert "程序入口" in html
    assert "加载并处理学生数据" in html


def test_render_does_not_rescan_injected_json_placeholders() -> None:
    bundle = build_architecture(ROOT)
    payload = "__APP_JS__ __CSS__ __TITLE__ __PROJECT_NAME__ __ARCHMAP_DATA_JSON__</script>\nnext"
    bundle["functionDetails"][0]["source"]["text"] = payload
    html = render_html(bundle)
    match = re.search(r"window\.__ARCHMAP_DATA__ = (.*?);\n</script>", html, re.S)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert embedded["functionDetails"][0]["source"]["text"] == payload
    assert "\\/script>" in match.group(1)


def test_render_contains_method_detail_contract() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "method-page" in html
    assert "method-source" in html
    assert "data-goto-method" in html
    assert "functionDetails" in html
    assert "functionFlows" not in html


def test_render_keeps_system_color_scheme_support() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "prefers-color-scheme: dark" in html
    assert "method-page" in html


def test_render_contains_class_component_contract() -> None:
    bundle = build_architecture(CLASS_ROOT)
    html = render_html(bundle)
    assert "renderModuleClassNode" in html
    assert "class-method-row" in html
    assert "cls:app.worker.EchoWorker" in html
    assert "抽象类/接口是契约节点" in html
