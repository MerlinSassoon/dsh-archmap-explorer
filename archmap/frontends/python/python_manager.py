"""Python language frontend facade manager."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config.project_config import ProjectConfig
from ...utility.config_utility import load_config
from ...model.analysis_model import AnalysisResult
from .analysis_utility import analyze_project
from .call_utility import collect_call_sites
from .contract_utility import build_capabilities
from .detail_utility import build_function_details as build_details
from .discovery_utility import discover_sources


class PythonFrontend:
    language = "python"
    file_suffixes = (".py",)

    def analyze(self, project_root: Path, config_path: Path | None = None) -> AnalysisResult:
        config = load_config(project_root, config_path)
        sources = discover_sources(config)
        return analyze_project(config, sources)

    def build_call_sites(self, analysis: Any) -> list[Any]:
        return collect_call_sites(analysis)

    def build_function_details(
        self, analysis: Any, call_sites: list[Any]
    ) -> list[dict[str, Any]]:
        return build_details(analysis, call_sites)

    def build_contracts(self, analysis: Any, call_sites: Any = None) -> Any:
        return build_capabilities(analysis, call_sites)
