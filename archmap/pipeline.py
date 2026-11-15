from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config
from .frontends import get_frontend
from .graph import build_bundle
from .layout import layout_function_flows


def build_architecture(project_root: Path, config_path: Path | None = None) -> dict[str, Any]:
    config = load_config(project_root, config_path)
    frontend = get_frontend(config.language)
    analysis = frontend.analyze(project_root, config_path)
    flows = frontend.build_flows(analysis)
    layout_function_flows(flows)
    return build_bundle(analysis, flows)
