"""Python-frontend capability projection stage implementation."""

from __future__ import annotations

from typing import Iterable

from ...config.contract_config import API_EXPOSING_ROLES
from ...model.analysis_model import AnalysisResult, ClassInfo, FunctionInfo
from ...model.call_model import CallSite
from ...model.contract_model import (
    ApiCapability,
    ClassRelation,
    ClassUsage,
    ContractModel,
    ProviderRoleInfo,
)
from ...utility.contract_utility import (
    _constructor_display,
    _function_capability,
    _protocol_capabilities,
)
from .role_utility import build_provider_roles


def _class_id(cls: ClassInfo) -> str:
    return f"cls:{cls.module_name}.{cls.qualname}"


def _method_name(capability: ApiCapability) -> str:
    if not capability.function_id:
        return capability.display
    return str(capability.function_id).split(".")[-1]


def _capability_key(capability: ApiCapability) -> tuple[str, str]:
    if capability.kind in {"method", "function"}:
        return "member", _method_name(capability)
    return "protocol", capability.kind


def _declared_class_capabilities(
    cls: ClassInfo, role_info: ProviderRoleInfo | None
) -> list[ApiCapability]:
    """Return only the capabilities declared by this class itself."""

    capabilities: list[ApiCapability] = []
    protocols, _ = _protocol_capabilities(cls, role_info)
    capabilities.extend(protocols)
    for method in sorted(cls.methods.values(), key=lambda item: (item.line, item.id)):
        if method.name.startswith("__") and method.name.endswith("__"):
            continue
        if method.api_exposure != "public":
            continue
        capabilities.append(_function_capability(method, role_info))
    return capabilities


def _inherited_display(base: ApiCapability, cls: ClassInfo) -> str:
    display = base.display or base.signature
    old_name = base.provider_name
    if old_name and display.startswith(old_name + "."):
        return cls.name + display[len(old_name):]
    if old_name and old_name in display:
        return display.replace(old_name, cls.name, 1)
    return display


def _inherit_capability(
    base: ApiCapability,
    cls: ClassInfo,
    role_info: ProviderRoleInfo | None,
) -> ApiCapability:
    class_id = _class_id(cls)
    init = cls.methods.get("__init__")
    constructor_id = init.id if init else None
    return ApiCapability(
        id=f"api:{class_id}:inherited:{base.id}",
        kind=base.kind,
        display=_inherited_display(base, cls),
        signature=base.signature,
        provider_id=class_id,
        provider_kind="class",
        provider_name=cls.name,
        module_id=cls.module_id,
        exposure=base.exposure,
        exposure_source=base.exposure_source,
        exposure_confidence=base.exposure_confidence,
        function_id=base.function_id,
        evidence_function_ids=list(base.evidence_function_ids),
        constructor_function_id=constructor_id,
        is_entry=False,
        note=base.note,
        file=base.file,
        line=base.line,
        end_line=base.end_line,
        provider_role=role_info.role if role_info else "utility",
        role_source=role_info.role_source if role_info else "structure",
        role_confidence=role_info.role_confidence if role_info else "medium",
        provider_visibility=role_info.provider_visibility if role_info else "internal",
        owner_provider_id=role_info.owner_provider_id if role_info else None,
        inherited=True,
        declared_in_provider_id=base.declared_in_provider_id or base.provider_id,
        inherited_from_provider_id=base.provider_id,
        inherited_from_class_ids=[base.provider_id],
    )


def _class_relations(analysis: AnalysisResult) -> list[ClassRelation]:
    class_by_id = {_class_id(cls): cls for cls in analysis.classes}
    relations: list[ClassRelation] = []
    for cls in sorted(analysis.classes, key=lambda item: _class_id(item)):
        for base_id in cls.base_class_ids:
            base = class_by_id.get(base_id)
            if base is None:
                continue
            kind = (
                "implements"
                if base.is_abstract or base.class_kind in {"abstract", "interface"}
                else "inherits"
            )
            relations.append(
                ClassRelation(
                    id=f"type:{_class_id(cls)}:{kind}:{base_id}",
                    kind=kind,
                    from_class_id=_class_id(cls),
                    to_class_id=base_id,
                    to_class_name=base.qualname,
                    module_id=cls.module_id,
                    target_module_id=base.module_id,
                    confidence="high",
                    evidence_file=cls.file,
                    evidence_line=cls.line,
                )
            )
    return relations


def build_capabilities(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite] | None = None,
) -> ContractModel:
    """Build the language-neutral API contract projection for Python.

    P3 adds resolved type relations and inherited capabilities.  Inherited
    capabilities remain owned by the subclass for module/API purposes, while
    ``declaredInProviderId`` and ``inheritedFromProviderId`` preserve the base
    declaration.  Sequence protocols remain intentionally deferred.
    """

    capabilities: list[ApiCapability] = []
    class_usage: dict[str, ClassUsage] = {}
    provider_roles = build_provider_roles(analysis, call_sites)
    class_by_id = {_class_id(cls): cls for cls in analysis.classes}
    declared_by_class: dict[str, list[ApiCapability]] = {}

    for cls in analysis.classes:
        class_id = _class_id(cls)
        role_info = provider_roles.get(class_id)
        role = role_info.role if role_info else "utility"
        if role_info is not None:
            role_info.base_class_ids = list(cls.base_class_ids)
            role_info.subclass_ids = list(cls.subclass_ids)
            role_info.mro_class_ids = list(cls.mro_class_ids)
            role_info.abstract_method_names = list(cls.abstract_method_names)
        _, protocols = _protocol_capabilities(cls, role_info)
        expose_apis = role in API_EXPOSING_ROLES and not cls.name.startswith("_")
        class_usage[class_id] = ClassUsage(
            class_id=class_id,
            module_id=cls.module_id,
            constructor_signature=_constructor_display(cls),
            constructor_function_id=(cls.methods.get("__init__").id if cls.methods.get("__init__") else None),
            protocols=protocols,
            provider_role=role,
            role_source=role_info.role_source if role_info else "structure",
            role_confidence=role_info.role_confidence if role_info else "medium",
            provider_visibility=role_info.provider_visibility if role_info else "internal",
            type_summary=role_info.type_summary if role_info else None,
            base_class_ids=list(cls.base_class_ids),
            subclass_ids=list(cls.subclass_ids),
            mro_class_ids=list(cls.mro_class_ids),
            abstract_method_names=list(cls.abstract_method_names),
        )
        if expose_apis:
            declared_by_class[class_id] = _declared_class_capabilities(cls, role_info)
        else:
            declared_by_class[class_id] = []

    for cls in analysis.classes:
        class_id = _class_id(cls)
        role_info = provider_roles.get(class_id)
        if not declared_by_class.get(class_id):
            continue
        own_caps = list(declared_by_class[class_id])
        effective = {_capability_key(cap): cap for cap in own_caps}
        for ancestor_id in cls.mro_class_ids[1:]:
            for base_cap in declared_by_class.get(ancestor_id, []):
                key = _capability_key(base_cap)
                existing = effective.get(key)
                if existing is None:
                    inherited = _inherit_capability(base_cap, cls, role_info)
                    effective[key] = inherited
                elif not existing.inherited and not existing.overrides_capability_id:
                    existing.overrides_capability_id = base_cap.id
        capabilities.extend(effective.values())

    protocol_kinds = {
        "context_manager",
        "async_context_manager",
        "callable",
        "iterable",
    }
    protocols_by_provider: dict[str, set[str]] = {}
    for capability in capabilities:
        if capability.kind in protocol_kinds:
            protocols_by_provider.setdefault(capability.provider_id, set()).add(capability.kind)
    for class_id, usage in class_usage.items():
        usage.protocols = sorted(protocols_by_provider.get(class_id, set()))

    for fn in analysis.functions:
        if fn.class_name:
            continue
        role_info = provider_roles.get(fn.id)
        role = role_info.role if role_info else "utility"
        if role not in API_EXPOSING_ROLES:
            continue
        if fn.api_exposure != "public":
            continue
        capabilities.append(_function_capability(fn, role_info))

    capabilities.sort(
        key=lambda item: (
            0 if item.provider_kind == "class" else 1,
            item.provider_name,
            item.kind,
            item.display,
            item.id,
        )
    )
    return ContractModel(
        capabilities=capabilities,
        class_usage=class_usage,
        provider_roles=provider_roles,
        class_relations=_class_relations(analysis),
    )
