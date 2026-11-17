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
    is_entry = fn.synthetic or fn.id in configured_entries or fn.name == "__main__"
    if unit_role == "utility":
        return "utility", "structure", "high"
    if unit_role == "manager":
        if is_entry:
            return "entry", "entrypoint" if fn.id in configured_entries else "structure", "high"
        return "utility", "structure", "high"
    if unit_role == "entry":
        if is_entry:
            return "entry", "entrypoint" if fn.id in configured_entries else "structure", "high"
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
    owners = _infer_owner_ids(analysis, call_sites)
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

    for fn in analysis.functions:
        if fn.class_name:
            continue
        provider_id = fn.id
        module = modules_by_name.get(fn.module_name)
        configured = _configured_role(
            analysis.config, provider_id, fn.module_name, fn.qualname, fn.name
        )
        if configured:
            role, source, confidence = configured, "config", "high"
        else:
            metadata = _metadata_role(fn.node, module.lines if module else [])
            if metadata:
                role, source, confidence = metadata
            else:
                unit_role = _code_unit_role_for_file(fn.file)
                from_unit = _function_role_from_unit(
                    fn, module, unit_role, configured_entries, project_names
                )
                role, source, confidence = from_unit or _infer_function_role(
                    fn, module, configured_entries, project_names
                )
        owner_provider_id = owners.get(fn.id)
        if owner_provider_id and role not in {"entry", "adapter", "component", "contract"}:
            role, source, confidence = "utility", "structure", "medium"
        if role == "utility":
            visibility = "internal"
        elif role == "entry":
            visibility = "public"
        else:
            visibility = _provider_visibility(role, fn.name, fn.api_exposure)
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
