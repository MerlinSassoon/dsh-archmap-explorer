from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MODULE_ROLES = {"main", "service", "adapter", "test", "other"}

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
    id: str
    name: str
    include: list[str] = field(default_factory=list)
    note: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    color: str = "#f59e0b"
    role: str = ""


@dataclass
class ProjectConfig:
    root: Path
    name: str
    language: str = "python"
    include: list[str] = field(default_factory=lambda: ["**/*.py"])
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    modules: list[ModuleConfig] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=lambda: ["用户输入"])
    outputs: list[str] = field(default_factory=lambda: ["用户输出"])
    max_functions: int = 2000
    max_steps: int = 300
    max_data_deps: int = 200
    contract_public_tags: list[str] = field(default_factory=lambda: list(DEFAULT_PUBLIC_API_TAGS))
    contract_internal_tags: list[str] = field(default_factory=lambda: list(DEFAULT_INTERNAL_API_TAGS))
    api_exposure_overrides: dict[str, str] = field(default_factory=dict)
    module_exports: dict[str, list[str]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _as_list(value: Any, fallback: list[str] | None = None) -> list[str]:
    if value is None:
        return list(fallback or [])
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def load_config(project_root: Path, config_path: Path | None = None) -> ProjectConfig:
    root = project_root.resolve()
    path = config_path
    if path is None:
        candidate = root / "archmap.config.json"
        if candidate.exists():
            path = candidate
    raw: dict[str, Any] = {}
    if path and path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))

    project_meta = raw.get("project") if isinstance(raw.get("project"), dict) else {}
    name = str(raw.get("projectName") or project_meta.get("name") or root.name)
    language = str(raw.get("language") or project_meta.get("language") or "python")
    include = _as_list(raw.get("include"), ["**/*.py"])
    exclude = _as_list(raw.get("exclude"), list(DEFAULT_EXCLUDES))
    entrypoints = _as_list(raw.get("entrypoints") or project_meta.get("entrypoints"))
    inputs = _as_list(project_meta.get("inputs") or raw.get("inputs"), ["用户输入"])
    outputs = _as_list(project_meta.get("outputs") or raw.get("outputs"), ["用户输出"])

    modules: list[ModuleConfig] = []
    for idx, item in enumerate(raw.get("modules") or []):
        if not isinstance(item, dict):
            continue
        module_id = str(item.get("id") or f"module-{idx + 1}")
        modules.append(
            ModuleConfig(
                id=module_id,
                name=str(item.get("name") or module_id),
                include=_as_list(item.get("include"), []),
                note=str(item.get("note") or ""),
                inputs=_as_list(item.get("inputs"), []),
                outputs=_as_list(item.get("outputs"), []),
                color=str(item.get("color") or "#f59e0b"),
                role=str(item.get("role") or "").strip().lower(),
            )
        )

    contract = raw.get("contract") if isinstance(raw.get("contract"), dict) else {}
    public_tags = _as_list(contract.get("publicTags"), DEFAULT_PUBLIC_API_TAGS)
    internal_tags = _as_list(contract.get("internalTags"), DEFAULT_INTERNAL_API_TAGS)
    exposure_overrides: dict[str, str] = {}
    raw_overrides = contract.get("apiExposure")
    if isinstance(raw_overrides, dict):
        for key, value in raw_overrides.items():
            normalized = str(value or "").strip().lower()
            if normalized in {"public", "internal"}:
                exposure_overrides[str(key)] = normalized
    module_exports: dict[str, list[str]] = {}
    raw_exports = contract.get("moduleExports")
    if isinstance(raw_exports, dict):
        for key, value in raw_exports.items():
            module_exports[str(key)] = _as_list(value, [])

    limits = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}
    return ProjectConfig(
        root=root,
        name=name,
        language=language,
        include=include,
        exclude=exclude,
        modules=modules,
        entrypoints=entrypoints,
        inputs=inputs,
        outputs=outputs,
        max_functions=int(limits.get("maxFunctions", 2000)),
        max_steps=int(limits.get("maxStepsPerFunction", 300)),
        max_data_deps=int(limits.get("maxDataDepsPerFunction", 200)),
        contract_public_tags=public_tags,
        contract_internal_tags=internal_tags,
        api_exposure_overrides=exposure_overrides,
        module_exports=module_exports,
        raw=raw,
    )
