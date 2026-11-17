from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config
from .frontends import get_frontend
from .graph import build_bundle


def build_architecture(project_root: Path, config_path: Path | None = None) -> dict[str, Any]:
    config = load_config(project_root, config_path)
    frontend = get_frontend(config.language)
    analysis = frontend.analyze(project_root, config_path)
    call_sites = frontend.build_call_sites(analysis)
    function_details = frontend.build_function_details(analysis, call_sites)
    contracts = frontend.build_contracts(analysis)
    return build_bundle(analysis, call_sites, function_details, contracts)
