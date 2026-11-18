"""Canonical source-analysis data models."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from ..config.project_config import ProjectConfig


@dataclass
class ImportRef:
    alias: str
    module: str
    name: str | None = None
    level: int = 0


@dataclass
class FunctionInfo:
    id: str
    name: str
    qualname: str
    module_name: str
    module_id: str
    file: str
    line: int
    end_line: int
    signature: str
    is_async: bool
    note: str
    node: ast.AST
    class_name: str | None = None
    source_file: SourceFile | None = None
    synthetic: bool = False
    method_kind: str = "function"
    visibility: str = "public"
    is_abstract: bool = False
    api_exposure: str = "public"
    api_exposure_source: str = "naming"
    api_exposure_confidence: str = "medium"


@dataclass
class ClassInfo:
    name: str
    qualname: str
    module_name: str
    node: ast.ClassDef
    methods: dict[str, FunctionInfo] = field(default_factory=dict)
    bases: list[str] = field(default_factory=list)
    module_id: str = ""
    file: str = ""
    line: int = 0
    end_line: int = 0
    note: str = ""
    decorators: list[str] = field(default_factory=list)
    is_abstract: bool = False
    class_kind: str = "service"
    # P3 type hierarchy facts.  Base strings are retained as source evidence;
    # *_class_ids/mro_class_ids are canonical IDs resolved by the frontend.
    base_class_ids: list[str] = field(default_factory=list)
    unresolved_bases: list[str] = field(default_factory=list)
    subclass_ids: list[str] = field(default_factory=list)
    mro_class_ids: list[str] = field(default_factory=list)
    abstract_method_names: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    name: str
    module_id: str
    file: SourceFile
    tree: ast.Module
    source: str
    lines: list[str]
    imports: dict[str, ImportRef] = field(default_factory=dict)
    functions: dict[str, FunctionInfo] = field(default_factory=dict)
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    top_level: list[ast.stmt] = field(default_factory=list)


@dataclass
class AnalysisResult:
    config: ProjectConfig
    modules: list[ModuleInfo]
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    diagnostics: list[dict[str, Any]]
    source_by_file: dict[str, str]
    line_cache: dict[str, list[str]]
    function_by_id: dict[str, FunctionInfo]
    function_by_qualname: dict[str, FunctionInfo]
    method_index: dict[tuple[str, str], FunctionInfo]
    # Explicit module-level callable exclusions from the capability surface.
    execution_only_function_ids: set[str] = field(default_factory=set)
    execution_only_module_by_function: dict[str, str] = field(default_factory=dict)
    # Effective P9 surface for module-level free functions. Values are
    # ``capability`` / ``internal`` / ``execution``; sources explain why.
    free_function_surfaces: dict[str, str] = field(default_factory=dict)
    free_function_surface_sources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel_path: str
    module_name: str
    module_id: str
