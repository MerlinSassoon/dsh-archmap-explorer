from __future__ import annotations

from pathlib import Path
from typing import Any

from ...analysis import AnalysisResult, analyze_project
from ...callsites import collect_call_sites
from ...config import load_config
from ...details import build_function_details as build_details
from ...discover import discover_sources
from .capabilities import build_capabilities


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

    def build_contracts(self, analysis: Any) -> Any:
        return build_capabilities(analysis)
