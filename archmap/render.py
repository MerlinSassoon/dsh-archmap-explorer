from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ASSET_DIR = Path(__file__).parent / "render" / "assets"


def _safe_json(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(bundle: dict[str, Any], annotations: dict[str, Any] | None = None) -> str:
    template = (ASSET_DIR / "index.html").read_text(encoding="utf-8")
    css = (ASSET_DIR / "app.css").read_text(encoding="utf-8")
    app_js = (ASSET_DIR / "app.js").read_text(encoding="utf-8")
    data = dict(bundle)
    if annotations is not None:
        data["annotations"] = annotations
    project_name = bundle.get("project", {}).get("name", "ArchMap")
    title = f"ArchMap · {project_name}"
    html = (
        template.replace("__TITLE__", str(title))
        .replace("__CSS__", css)
        .replace("__PROJECT_NAME__", str(project_name))
        .replace("__ARCHMAP_DATA_JSON__", _safe_json(data))
        .replace("__APP_JS__", app_js)
    )
    return html
