"""Python-frontend capability projection stage implementation."""

from __future__ import annotations

from typing import Iterable

from ...config.contract_config import API_EXPOSING_ROLES
from ...model.analysis_model import AnalysisResult
from ...model.call_model import CallSite
from ...model.contract_model import ApiCapability, ClassUsage, ContractModel
from ...utility.contract_utility import (
    _constructor_display,
    _function_capability,
    _protocol_capabilities,
)
from .role_utility import build_provider_roles


def build_capabilities(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite] | None = None,
) -> ContractModel:
    """Build the language-neutral API contract projection for Python.

    Magic methods are excluded from ordinary method capabilities.  Protocol
    pairs are synthesized into capabilities (context manager, callable,
    iterable), while sequence protocols such as ``__len__`` and
    ``__getitem__`` are intentionally deferred until a later phase.
    """
    capabilities: list[ApiCapability] = []
    class_usage: dict[str, ClassUsage] = {}
    provider_roles = build_provider_roles(analysis, call_sites)

    for cls in analysis.classes:
        class_id = f"cls:{cls.module_name}.{cls.qualname}"
        role_info = provider_roles.get(class_id)
        role = role_info.role if role_info else "utility"
        protocol_caps, protocols = _protocol_capabilities(cls, role_info)
        # config/model are type-definition providers.  Their serialization or
        # convenience methods are implementation details, not module APIs.
        expose_apis = role in API_EXPOSING_ROLES and not cls.name.startswith("_")
        if expose_apis:
            capabilities.extend(protocol_caps)
        init = cls.methods.get("__init__")
        class_usage[class_id] = ClassUsage(
            class_id=class_id,
            module_id=cls.module_id,
            constructor_signature=_constructor_display(cls),
            constructor_function_id=init.id if init else None,
            protocols=protocols,
            provider_role=role,
            role_source=role_info.role_source if role_info else "structure",
            role_confidence=role_info.role_confidence if role_info else "medium",
            provider_visibility=role_info.provider_visibility if role_info else "internal",
            type_summary=role_info.type_summary if role_info else None,
        )
        if not expose_apis:
            continue
        for method in cls.methods.values():
            if method.name.startswith("__") and method.name.endswith("__"):
                continue
            if method.api_exposure != "public":
                continue
            capabilities.append(_function_capability(method, role_info))

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
    )
