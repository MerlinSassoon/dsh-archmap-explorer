"""Configuration loading and parsing helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.contract_config import PROVIDER_ROLES
from ..config.project_config import (
    DEFAULT_EXCLUDES,
    DEFAULT_INTERNAL_API_TAGS,
    DEFAULT_PUBLIC_API_TAGS,
    MODULE_KINDS,
    DispatchHint,
    ModuleConfig,
    ProjectConfig,
)


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
    main_module_id = str(
        raw.get("mainModule") or project_meta.get("mainModule") or ""
    ).strip()

    modules: list[ModuleConfig] = []
    for idx, item in enumerate(raw.get("modules") or []):
        if not isinstance(item, dict):
            continue
        module_id = str(item.get("id") or f"module-{idx + 1}")
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in MODULE_KINDS:
            kind = "main" if item.get("main") is True else ""
        modules.append(
            ModuleConfig(
                id=module_id,
                name=str(item.get("name") or module_id),
                include=_as_list(item.get("include"), []),
                note=str(item.get("note") or ""),
                color=str(item.get("color") or "#f59e0b"),
                role=str(item.get("role") or "").strip().lower(),
                kind=kind,
            )
        )

    if not main_module_id:
        main_module_id = next(
            (module.id for module in modules if module.kind == "main" or module.role == "main"),
            modules[0].id if modules else "",
        )
    for module in modules:
        module.kind = "main" if module.id == main_module_id else "functional"
        if not module.role:
            module.role = "main" if module.kind == "main" else "service"

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
    provider_roles: dict[str, str] = {}
    raw_provider_roles = contract.get("providerRoles")
    if isinstance(raw_provider_roles, dict):
        for key, value in raw_provider_roles.items():
            normalized = str(value or "").strip().lower()
            if normalized in PROVIDER_ROLES:
                provider_roles[str(key)] = normalized
    module_exports: dict[str, list[str]] = {}
    raw_exports = contract.get("moduleExports")
    if isinstance(raw_exports, dict):
        for key, value in raw_exports.items():
            module_exports[str(key)] = _as_list(value, [])

    dispatch_hints: list[DispatchHint] = []
    main_flow = raw.get("mainFlow") if isinstance(raw.get("mainFlow"), dict) else {}
    for item in main_flow.get("dispatches") or []:
        if not isinstance(item, dict):
            continue
        function = str(item.get("function") or "").strip()
        if not function:
            continue
        dispatch_hints.append(
            DispatchHint(
                function=function,
                expression=str(item.get("expression") or "").strip(),
                occurrence=max(1, int(item.get("occurrence", 1) or 1)),
                candidates=_as_list(item.get("candidates"), []),
                complete=bool(item.get("complete", False)),
                reason=str(item.get("reason") or "config"),
            )
        )

    limits = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}
    return ProjectConfig(
        root=root,
        name=name,
        language=language,
        include=include,
        exclude=exclude,
        modules=modules,
        entrypoints=entrypoints,
        main_module_id=main_module_id,
        dispatch_hints=dispatch_hints,
        max_functions=int(limits.get("maxFunctions", 2000)),
        max_steps=int(limits.get("maxStepsPerFunction", 300)),
        max_data_deps=int(limits.get("maxDataDepsPerFunction", 200)),
        contract_public_tags=public_tags,
        contract_internal_tags=internal_tags,
        api_exposure_overrides=exposure_overrides,
        provider_role_overrides=provider_roles,
        module_exports=module_exports,
        raw=raw,
    )
