from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from .config import ModuleConfig, ProjectConfig


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel_path: str
    module_name: str
    module_id: str


def _matches(rel: str, patterns: list[str]) -> bool:
    # fnmatch's ``**/dir/**`` form does not match a root-level ``dir/...``
    # because the leading slash is absent.  Test both the plain relative path
    # and a slash-prefixed form so default excludes work at any depth.
    candidate = "/" + rel.lstrip("/")
    return any(
        fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(candidate, pattern)
        for pattern in patterns
    )


def module_name_for(rel_path: str) -> str:
    path = Path(rel_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else path.stem


def _assign_module(rel_path: str, module_configs: list[ModuleConfig]) -> str:
    for module in module_configs:
        if module.include and _matches(rel_path, module.include):
            return module.id
    if module_configs:
        return module_configs[0].id
    return "main"


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
                module_name=module_name_for(rel),
                module_id=module_id,
            )
        )
    return result
