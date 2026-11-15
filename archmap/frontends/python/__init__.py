from __future__ import annotations

from pathlib import Path
from typing import Any

from ...analysis import AnalysisResult, analyze_project
from ...config import load_config
from ...discover import discover_sources
from ...flow import build_function_flows


class PythonFrontend:
    language = "python"
    file_suffixes = (".py",)

    def analyze(self, project_root: Path, config_path: Path | None = None) -> AnalysisResult:
        config = load_config(project_root, config_path)
        sources = discover_sources(config)
        return analyze_project(config, sources)

    def build_flows(self, analysis: Any) -> list[dict[str, Any]]:
        return build_function_flows(analysis)
