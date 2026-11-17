"""HTML rendering facade manager."""

from __future__ import annotations

from typing import Any

from ..utility.render_utility import render_html


class RenderManager:
    """Facade for self-contained HTML rendering."""

    def render(self, bundle: dict[str, Any], annotations: dict[str, Any] | None = None) -> str:
        return render_html(bundle, annotations)
