"""Application pipeline implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..managers.frontend_manager import FrontendManager
from ..managers.graph_manager import GraphManager
from ..utility.config_utility import load_config


def build_architecture(
    project_root: Path, config_path: Path | None = None
) -> dict[str, Any]:
    config = load_config(project_root, config_path)
    frontend = FrontendManager().get(config.language)
    analysis = frontend.analyze(project_root, config_path)
    call_sites = frontend.build_call_sites(analysis)
    function_details = frontend.build_function_details(analysis, call_sites)
    contracts = frontend.build_contracts(analysis, call_sites)
    return GraphManager().build_bundle(analysis, call_sites, function_details, contracts)
