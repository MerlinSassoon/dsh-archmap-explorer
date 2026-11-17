"""Compatibility shim for the pre-P2.3 pipeline module."""

from pathlib import Path
from typing import Any

from .managers.pipeline_manager import PipelineManager


def build_architecture(
    project_root: Path, config_path: Path | None = None
) -> dict[str, Any]:
    return PipelineManager().build_architecture(project_root, config_path)


__all__ = ["build_architecture"]
