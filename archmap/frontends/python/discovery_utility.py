"""Python-frontend source-discovery stage implementation."""

from __future__ import annotations

from ...config.project_config import ProjectConfig
from ...model.analysis_model import SourceFile
from ...utility.discovery_utility import _assign_module, _matches
from ...utility.discovery_utility import _module_name_for


def discover_sources(config: ProjectConfig) -> list[SourceFile]:
    root = config.root
    found: set[Path] = set()
    for pattern in config.include:
        for path in root.glob(pattern):
            if path.is_file() and path.suffix == ".py":
                found.add(path.resolve())
    result: list[SourceFile] = []
    for path in sorted(found):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if _matches(rel, config.exclude):
            continue
        module_id = _assign_module(rel, config.modules)
        result.append(
            SourceFile(
                path=path,
                rel_path=rel,
                module_name=_module_name_for(rel),
                module_id=module_id,
            )
        )
    return result
