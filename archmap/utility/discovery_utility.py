"""Source-discovery and module-assignment helpers."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from ..config.project_config import ModuleConfig


def _matches(rel: str, patterns: list[str]) -> bool:
    # fnmatch's ``**/dir/**`` form does not match a root-level ``dir/...``
    # because the leading slash is absent.  Test both the plain relative path
    # and a slash-prefixed form so default excludes work at any depth.
    candidate = "/" + rel.lstrip("/")
    return any(
        fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(candidate, pattern)
        for pattern in patterns
    )


def _module_name_for(rel_path: str) -> str:
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
