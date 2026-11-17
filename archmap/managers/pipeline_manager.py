"""Application pipeline facade manager."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utility.pipeline_utility import build_architecture


class PipelineManager:
    """Application facade for config → frontend → graph orchestration."""

    def build_architecture(
        self, project_root: Path, config_path: Path | None = None
    ) -> dict[str, Any]:
        return build_architecture(project_root, config_path)
