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
    DispatchHint,
    FlowScopeConfig,
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
    execution_entrypoints = _as_list(
        raw.get("executionEntrypoints") or project_meta.get("executionEntrypoints")
    )
    legacy_main_module = str(
        raw.get("mainModule") or project_meta.get("mainModule") or ""
    ).strip()
    config_diagnostics: list[dict[str, Any]] = []
    if legacy_main_module:
        config_diagnostics.append(
            {
                "severity": "warning",
                "code": "MAIN_MODULE_DEPRECATED",
                "message": "mainModule is ignored by schema 5.0; all modules are ordinary capability modules.",
            }
        )

    modules: list[ModuleConfig] = []
    for idx, item in enumerate(raw.get("modules") or []):
        if not isinstance(item, dict):
            continue
        module_id = str(item.get("id") or f"module-{idx + 1}")
        legacy_kind = str(item.get("kind") or "").strip().lower()
        legacy_main = legacy_kind == "main" or item.get("main") is True
        if legacy_kind:
            config_diagnostics.append(
                {
                    "severity": "warning",
                    "code": "MODULE_KIND_DEPRECATED",
                    "message": f"module {module_id} uses deprecated kind={legacy_kind!r}; schema 5.0 removes moduleKind.",
                }
            )
        role = str(item.get("role") or "").strip().lower()
        if role in {"main", "entry"}:
            config_diagnostics.append(
                {
                    "severity": "warning",
                    "code": "MODULE_ENTRY_ROLE_DEPRECATED",
                    "message": f"module {module_id} role={role!r} is deprecated; modules no longer carry entry semantics.",
                }
            )
            role = "service"
        if not role and (legacy_main or module_id == legacy_main_module):
            role = "service"
        default_free_function_surface = str(
            item.get("defaultFreeFunctionSurface") or "auto"
        ).strip().lower()
        if default_free_function_surface not in {"auto", "internal", "capability"}:
            config_diagnostics.append(
                {
                    "severity": "warning",
                    "code": "DEFAULT_FREE_FUNCTION_SURFACE_INVALID",
                    "message": (
                        f"module {module_id} defaultFreeFunctionSurface="
                        f"{default_free_function_surface!r} is invalid; falling back to auto"
                    ),
                }
            )
            default_free_function_surface = "auto"
        modules.append(
            ModuleConfig(
                id=module_id,
                name=str(item.get("name") or module_id),
                include=_as_list(item.get("include"), []),
                note=str(item.get("note") or ""),
                color=str(item.get("color") or "#f59e0b"),
                role=role,
                default_free_function_surface=default_free_function_surface,
                execution_only_callables=_as_list(item.get("executionOnlyCallables"), []),
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
    provider_roles: dict[str, str] = {}
    raw_provider_roles = contract.get("providerRoles")
    if isinstance(raw_provider_roles, dict):
        for key, value in raw_provider_roles.items():
            normalized = str(value or "").strip().lower()
            if normalized == "entry":
                config_diagnostics.append(
                    {
                        "severity": "warning",
                        "code": "PROVIDER_ENTRY_ROLE_DEPRECATED",
                        "message": f"provider {key} uses deprecated role 'entry'; flow entry status is now project-level.",
                    }
                )
                continue
            if normalized in PROVIDER_ROLES:
                provider_roles[str(key)] = normalized
    module_exports: dict[str, list[str]] = {}
    raw_exports = contract.get("moduleExports")
    if isinstance(raw_exports, dict):
        for key, value in raw_exports.items():
            module_exports[str(key)] = _as_list(value, [])

    user_surface_overrides: list[dict[str, Any]] = []
    user_surface = raw.get("userSurface") if isinstance(raw.get("userSurface"), dict) else {}
    for item in user_surface.get("overrides") or []:
        if not isinstance(item, dict):
            continue
        function = str(item.get("function") or "").strip()
        kind = str(item.get("kind") or "").strip().lower()
        if not function or not kind:
            continue
        audiences = _as_list(item.get("audiences") or item.get("audience"), ["end_user"])
        user_surface_overrides.append(
            {
                "function": function,
                "kind": kind,
                "display": str(item.get("display") or ""),
                "audiences": audiences,
                "confidence": str(item.get("confidence") or "high").strip().lower(),
                "source": "config",
            }
        )

    dispatch_hints: list[DispatchHint] = []
    main_flow = raw.get("mainFlow") if isinstance(raw.get("mainFlow"), dict) else {}
    raw_dispatch_hints = raw.get("dispatchHints")
    if raw_dispatch_hints is None:
        raw_dispatch_hints = main_flow.get("dispatches")
    if not isinstance(raw_dispatch_hints, list):
        raw_dispatch_hints = []
    for item in raw_dispatch_hints:
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

    flow_scopes_raw = raw.get("flowScopes")
    flow_scopes = FlowScopeConfig()
    if isinstance(flow_scopes_raw, dict):
        flow_scopes.enabled = bool(flow_scopes_raw.get("enabled", True))
        flow_scopes.roots = _as_list(flow_scopes_raw.get("roots"), [])
        flow_scopes.auto_detect = bool(flow_scopes_raw.get("autoDetect", False))

        def _positive_int(name: str, fallback: int, maximum: int) -> int:
            value = flow_scopes_raw.get(name, fallback)
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = fallback
                config_diagnostics.append(
                    {
                        "severity": "warning",
                        "code": "FLOW_SCOPE_LIMIT_INVALID",
                        "message": f"flowScopes.{name}={value!r} is invalid; falling back to {fallback}",
                    }
                )
            if parsed < 1:
                config_diagnostics.append(
                    {
                        "severity": "warning",
                        "code": "FLOW_SCOPE_LIMIT_INVALID",
                        "message": f"flowScopes.{name}={parsed} must be positive; falling back to {fallback}",
                    }
                )
                parsed = fallback
            return min(parsed, maximum)

        flow_scopes.max_scopes_per_flow = _positive_int("maxScopesPerFlow", 6, 20)
        flow_scopes.max_nodes_per_scope = _positive_int("maxNodesPerScope", 24, 80)
        flow_scopes.max_edges_per_scope = _positive_int("maxEdgesPerScope", 32, 120)

    limits = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}
    return ProjectConfig(
        root=root,
        name=name,
        language=language,
        include=include,
        exclude=exclude,
        modules=modules,
        entrypoints=entrypoints,
        execution_entrypoints=execution_entrypoints,
        dispatch_hints=dispatch_hints,
        flow_scopes=flow_scopes,
        config_diagnostics=config_diagnostics,
        max_functions=int(limits.get("maxFunctions", 2000)),
        max_steps=int(limits.get("maxStepsPerFunction", 300)),
        max_data_deps=int(limits.get("maxDataDepsPerFunction", 200)),
        contract_public_tags=public_tags,
        contract_internal_tags=internal_tags,
        api_exposure_overrides=exposure_overrides,
        provider_role_overrides=provider_roles,
        module_exports=module_exports,
        user_surface_overrides=user_surface_overrides,
        raw=raw,
    )
