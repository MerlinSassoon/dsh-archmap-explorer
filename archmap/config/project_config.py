"""Project and module configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contract_config import PROVIDER_ROLES


MODULE_ROLES = {"main", "service", "adapter", "test", "other"}
MODULE_KINDS = {"main", "functional"}

DEFAULT_PUBLIC_API_TAGS = [
    "公开API",
    "公开 API",
    "public API",
    "@public",
]

DEFAULT_INTERNAL_API_TAGS = [
    "内部API",
    "内部 API",
    "internal API",
    "@internal",
]

DEFAULT_EXCLUDES = [
    "**/__pycache__/**",
    "**/.git/**",
    "**/.venv/**",
    "**/venv/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/build/**",
    "**/dist/**",
]


@dataclass
class ModuleConfig:
    """A logical module in the project composition."""

    id: str
    name: str
    include: list[str] = field(default_factory=list)
    note: str = ""
    color: str = "#f59e0b"
    role: str = ""
    kind: str = ""


@dataclass
class DispatchHint:
    """Declared candidate set for one dynamic dispatch site."""

    function: str
    expression: str = ""
    occurrence: int = 1
    candidates: list[str] = field(default_factory=list)
    complete: bool = False
    reason: str = ""


@dataclass
class ProjectConfig:
    root: Path
    name: str
    language: str = "python"
    include: list[str] = field(default_factory=lambda: ["**/*.py"])
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    modules: list[ModuleConfig] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    main_module_id: str = ""
    dispatch_hints: list[DispatchHint] = field(default_factory=list)
    max_functions: int = 2000
    max_steps: int = 300
    max_data_deps: int = 200
    contract_public_tags: list[str] = field(default_factory=lambda: list(DEFAULT_PUBLIC_API_TAGS))
    contract_internal_tags: list[str] = field(default_factory=lambda: list(DEFAULT_INTERNAL_API_TAGS))
    api_exposure_overrides: dict[str, str] = field(default_factory=dict)
    provider_role_overrides: dict[str, str] = field(default_factory=dict)
    module_exports: dict[str, list[str]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
