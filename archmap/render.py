"""Compatibility shim for the pre-P2.3 render module."""

from .utility.render_utility import (
    RENDER_ASSET_DIR,
    _fill_template,
    _safe_json,
    render_html,
)

__all__ = ["RENDER_ASSET_DIR", "_fill_template", "_safe_json", "render_html"]
