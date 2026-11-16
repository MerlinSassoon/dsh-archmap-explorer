from __future__ import annotations

import json
import re
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


def _fill_template(template: str, values: dict[str, str]) -> str:
    """Replace template tokens in one pass.

    ``str.replace`` chains rescan content inserted by earlier replacements. That
    corrupts self-referential bundles when an analyzed code snippet contains a
    template token such as ``__APP_JS__``. ``re.sub`` does not rescan replacement
    text, so JSON, CSS and JavaScript are inserted exactly once and literally.
    """
    pattern = re.compile("|".join(re.escape(token) for token in sorted(values, key=len, reverse=True)))
    return pattern.sub(lambda match: values[match.group(0)], template)


def render_html(bundle: dict[str, Any], annotations: dict[str, Any] | None = None) -> str:
    template = (ASSET_DIR / "index.html").read_text(encoding="utf-8")
    css = (ASSET_DIR / "app.css").read_text(encoding="utf-8")
    app_js = (ASSET_DIR / "app.js").read_text(encoding="utf-8")
    data = dict(bundle)
    if annotations is not None:
        data["annotations"] = annotations
    project_name = bundle.get("project", {}).get("name", "ArchMap")
    title = f"ArchMap · {project_name}"
    return _fill_template(
        template,
        {
            "__TITLE__": str(title),
            "__CSS__": css,
            "__PROJECT_NAME__": str(project_name),
            "__ARCHMAP_DATA_JSON__": _safe_json(data),
            "__APP_JS__": app_js,
        },
    )
