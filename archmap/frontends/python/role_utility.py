"""Python-frontend provider-role stage implementation."""

from __future__ import annotations

from typing import Iterable

from ...model.analysis_model import AnalysisResult
from ...model.call_model import CallSite
from ...model.contract_model import ProviderRoleInfo
from ...utility.role_utility import (
    _code_unit_role_for_file,
    _configured_entry_ids,
    _configured_role,
    _infer_class_role,
    _infer_function_role,
    _infer_owner_ids,
    _metadata_role,
    _provider_visibility,
    _type_summary,
)


def _class_role_from_unit(
    cls,
    module,
    unit_role: str | None,
) -> tuple[str, str, str] | None:
    if unit_role == "utility":
        return "utility", "structure", "high"
    if unit_role == "config":
        return "config", "structure", "high"
    if unit_role == "model":
        inferred = _infer_class_role(cls, module)
        if inferred[0] == "contract":
            return inferred
        return "model", "structure", "high"
    if unit_role == "manager":
        inferred = _infer_class_role(cls, module)
        if inferred[0] in {"contract", "adapter", "component"}:
            return inferred
        return "manager", "structure", "high"
    return None


def _function_role_from_unit(
    fn,
    module,
    unit_role: str | None,
    configured_entries: set[str],
    project_names: set[str],
) -> tuple[str, str, str] | None:
    if unit_role == "utility":
        return "utility", "structure", "high"
    if unit_role == "manager":
        return "utility", "structure", "high"
    return None


def build_provider_roles(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite] | None = None,
) -> dict[str, ProviderRoleInfo]:
    """Infer Provider roles with normalized-file hints and ownership evidence.

    Explicit configuration wins.  For ArchMap's own normalized code units, the
    file suffix is a strong structural signal.  Legacy projects fall back to
    metadata and AST heuristics.  Resolved call sites then assign free functions
    to a single owning manager where possible and demote single-owner helpers to
    internal utility execution units.
    """
    configured_entries = _configured_entry_ids(analysis)
    modules_by_name = {module.name: module for module in analysis.modules}
    project_names = {
        fn.name for fn in analysis.functions if not fn.class_name
    } | {cls.name for cls in analysis.classes}
    module_configs = {module.id: module for module in analysis.config.modules}
    call_site_list = list(call_sites or [])
    incoming_modules_by_function: dict[str, set[str]] = {}
    function_by_id = {fn.id: fn for fn in analysis.functions}
    for site in call_site_list:
        if not site.resolved or not site.to_function_id:
            continue
        target = function_by_id.get(site.to_function_id)
        if target is None or target.class_name:
            continue
        incoming_modules_by_function.setdefault(target.id, set()).add(
            site.from_module_id
        )
    owners = _infer_owner_ids(analysis, call_site_list)
    roles: dict[str, ProviderRoleInfo] = {}

    for cls in analysis.classes:
        provider_id = f"cls:{cls.module_name}.{cls.qualname}"
        module = modules_by_name.get(cls.module_name)
        configured = _configured_role(
            analysis.config, provider_id, cls.module_name, cls.qualname, cls.name
        )
        if configured:
            role, source, confidence = configured, "config", "high"
        else:
            metadata = _metadata_role(cls.node, module.lines if module else [])
            if metadata:
                role, source, confidence = metadata
            else:
                unit_role = _code_unit_role_for_file(cls.file)
                from_unit = _class_role_from_unit(cls, module, unit_role)
                role, source, confidence = from_unit or _infer_class_role(cls, module)
        type_summary = _type_summary(cls, role) if role in {"config", "model"} else None
        visibility = "internal" if role == "utility" else _provider_visibility(role, cls.name, "public")
        roles[provider_id] = ProviderRoleInfo(
            provider_id=provider_id,
            provider_kind="class",
            provider_name=cls.name,
            module_id=cls.module_id,
            role=role,
            role_source=source,
            role_confidence=confidence,
            provider_visibility=visibility,
            owner_provider_id=None,
            type_summary=type_summary,
        )

    execution_only_ids = set(analysis.execution_only_function_ids)
    for fn in analysis.functions:
        if fn.class_name:
            continue
        provider_id = fn.id
        module = modules_by_name.get(fn.module_name)
        module_config = module_configs.get(fn.module_id)
        configured = _configured_role(
            analysis.config, provider_id, fn.module_name, fn.qualname, fn.name
        )
        metadata = _metadata_role(fn.node, module.lines if module else [])
        unit_role = _code_unit_role_for_file(fn.file)
        if configured:
            role, source, confidence = configured, "config", "high"
        elif metadata:
            role, source, confidence = metadata
        else:
            from_unit = _function_role_from_unit(
                fn, module, unit_role, configured_entries, project_names
            )
            role, source, confidence = from_unit or _infer_function_role(
                fn, module, configured_entries, project_names
            )

        if provider_id in execution_only_ids:
            surface, surface_source = "execution", "config"
        elif fn.api_exposure == "internal":
            surface, surface_source = "internal", "exposure"
        elif configured:
            surface = "internal" if configured == "utility" else "capability"
            surface_source = "config"
        elif metadata:
            surface = "internal" if role == "utility" else "capability"
            surface_source = "metadata"
        elif unit_role in {"utility", "manager"}:
            surface, surface_source = "internal", "file_unit"
        elif (
            fn.api_exposure == "public"
            and fn.api_exposure_source in {"docstring", "comment", "decorator", "config"}
        ):
            surface, surface_source = "capability", "exposure"
        else:
            default_surface = (
                module_config.default_free_function_surface
                if module_config is not None
                else "auto"
            )
            if default_surface == "internal":
                surface, surface_source = "internal", "module_default"
            elif default_surface == "capability":
                surface, surface_source = "capability", "module_default"
            else:
                incoming_modules = incoming_modules_by_function.get(fn.id, set())
                if any(source_module != fn.module_id for source_module in incoming_modules):
                    surface, surface_source = "capability", "call_graph"
                else:
                    surface, surface_source = "internal", "structure"

        analysis.free_function_surfaces[fn.id] = surface
        analysis.free_function_surface_sources[fn.id] = surface_source

        if surface != "capability":
            role, source, confidence = "utility", "surface", "high"
        elif role == "utility":
            role, source, confidence = "manager", "surface", (
                "high" if surface_source in {"config", "module_default", "exposure"} else "medium"
            )

        owner_provider_id = owners.get(fn.id)
        # Ownership compression is an implementation concern.  It hides
        # private helpers behind their facade manager but never erases a public
        # API surface.  Schema 5.0 has no special main-module compression rule.
        should_compress = (
            role not in {"adapter", "component", "contract"}
            and fn.api_exposure != "public"
        )
        if owner_provider_id and should_compress:
            role, source, confidence = "utility", "structure", "medium"
        elif owner_provider_id and role != "utility":
            owner_provider_id = None
        if surface != "capability" or role == "utility":
            visibility = "internal"
        else:
            visibility = "public"
        roles[provider_id] = ProviderRoleInfo(
            provider_id=provider_id,
            provider_kind="function",
            provider_name=fn.name,
            module_id=fn.module_id,
            role=role,
            role_source=source,
            role_confidence=confidence,
            provider_visibility=visibility,
            owner_provider_id=owner_provider_id,
            type_summary=None,
        )
    return roles
