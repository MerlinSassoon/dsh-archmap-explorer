"""Project and module configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contract_config import PROVIDER_ROLES


MODULE_ROLES = {"service", "adapter", "component", "test", "other"}

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
    # Default capability presentation for module-level free functions.
    # ``auto`` uses conservative evidence; explicit public API tags and
    # cross-module calls still win.
    default_free_function_surface: str = "auto"
    # Callables that remain part of the module's source boundary and execution
    # flows but are transparent to the module capability surface.
    execution_only_callables: list[str] = field(default_factory=list)


@dataclass
class FlowScopeConfig:
    """Configuration for one-level execution-flow interface drilldown."""

    enabled: bool = False
    roots: list[str] = field(default_factory=list)
    # Conservative auto-discovery of local free_function orchestration
    # callables. Interface nodes remain black-box and are never discovered.
    auto_detect: bool = False
    max_scopes_per_flow: int = 6
    max_nodes_per_scope: int = 24
    max_edges_per_scope: int = 32


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
    execution_entrypoints: list[str] = field(default_factory=list)
    dispatch_hints: list[DispatchHint] = field(default_factory=list)
    flow_scopes: FlowScopeConfig = field(default_factory=FlowScopeConfig)
    config_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    max_functions: int = 2000
    max_steps: int = 300
    max_data_deps: int = 200
    contract_public_tags: list[str] = field(default_factory=lambda: list(DEFAULT_PUBLIC_API_TAGS))
    contract_internal_tags: list[str] = field(default_factory=lambda: list(DEFAULT_INTERNAL_API_TAGS))
    api_exposure_overrides: dict[str, str] = field(default_factory=dict)
    provider_role_overrides: dict[str, str] = field(default_factory=dict)
    module_exports: dict[str, list[str]] = field(default_factory=dict)
    user_surface_overrides: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
