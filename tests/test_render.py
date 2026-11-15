from __future__ import annotations

from pathlib import Path

from archmap.pipeline import build_architecture
from archmap.render import render_html

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


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
                "sourceHash": bundle["functionFlows"][0]["sourceHash"],
            }
        },
    }
    html = render_html(bundle, annotations)
    assert "程序入口" in html
    assert "加载并处理学生数据" in html
