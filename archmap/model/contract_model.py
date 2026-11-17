"""Language-neutral provider and capability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderRoleInfo:
    """Resolved responsibility for a class or module-level function provider."""

    provider_id: str
    provider_kind: str
    provider_name: str
    module_id: str
    role: str
    role_source: str
    role_confidence: str
    provider_visibility: str = "public"
    owner_provider_id: str | None = None
    type_summary: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "providerRole": self.role,
            "roleSource": self.role_source,
            "roleConfidence": self.role_confidence,
            "providerVisibility": self.provider_visibility,
            "ownerProviderId": self.owner_provider_id,
            "typeSummary": self.type_summary,
        }


@dataclass
class ApiCapability:
    """A language-neutral public/internal contract capability.

    Providers are classes or free functions.  A provider may expose several
    capabilities: ordinary methods/functions plus synthesized protocol
    capabilities such as context managers or iterables.  Magic methods are
    evidence for protocol capabilities, not individual public APIs.
    """

    id: str
    kind: str
    display: str
    signature: str
    provider_id: str
    provider_kind: str
    provider_name: str
    module_id: str
    exposure: str = "public"
    exposure_source: str = "naming"
    exposure_confidence: str = "medium"
    function_id: str | None = None
    evidence_function_ids: list[str] = field(default_factory=list)
    constructor_function_id: str | None = None
    is_entry: bool = False
    note: str = ""
    file: str = ""
    line: int = 0
    end_line: int = 0
    provider_role: str = "utility"
    role_source: str = "structure"
    role_confidence: str = "medium"
    provider_visibility: str = "internal"
    owner_provider_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "display": self.display,
            "signature": self.signature,
            "providerId": self.provider_id,
            "providerKind": self.provider_kind,
            "providerName": self.provider_name,
            "providerRole": self.provider_role,
            "roleSource": self.role_source,
            "roleConfidence": self.role_confidence,
            "providerVisibility": self.provider_visibility,
            "ownerProviderId": self.owner_provider_id,
            "moduleId": self.module_id,
            "exposure": self.exposure,
            "exposureSource": self.exposure_source,
            "exposureConfidence": self.exposure_confidence,
            "functionId": self.function_id,
            "evidenceFunctionIds": list(self.evidence_function_ids),
            "constructorFunctionId": self.constructor_function_id,
            "isEntry": self.is_entry,
            "note": self.note,
            "file": self.file,
            "line": self.line,
            "endLine": self.end_line,
        }


@dataclass
class ClassUsage:
    """How consumers construct and use a class."""

    class_id: str
    module_id: str
    constructor_signature: str = ""
    constructor_function_id: str | None = None
    protocols: list[str] = field(default_factory=list)
    provider_role: str = "manager"
    role_source: str = "structure"
    role_confidence: str = "medium"
    provider_visibility: str = "public"
    owner_provider_id: str | None = None
    type_summary: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "constructor": {
                "functionId": self.constructor_function_id,
                "signature": self.constructor_signature,
            },
            "protocols": list(self.protocols),
            "providerRole": self.provider_role,
            "roleSource": self.role_source,
            "roleConfidence": self.role_confidence,
            "providerVisibility": self.provider_visibility,
            "ownerProviderId": self.owner_provider_id,
            "typeSummary": self.type_summary,
        }


@dataclass
class ContractModel:
    """Frontend-owned contract projection consumed by the neutral graph layer."""

    capabilities: list[ApiCapability] = field(default_factory=list)
    class_usage: dict[str, ClassUsage] = field(default_factory=dict)
    provider_roles: dict[str, ProviderRoleInfo] = field(default_factory=dict)

    def capabilities_by_provider(self) -> dict[str, list[ApiCapability]]:
        grouped: dict[str, list[ApiCapability]] = {}
        for capability in self.capabilities:
            grouped.setdefault(capability.provider_id, []).append(capability)
        for items in grouped.values():
            items.sort(key=lambda item: (item.kind, item.display, item.id))
        return grouped

    def capabilities_by_module(self) -> dict[str, list[ApiCapability]]:
        grouped: dict[str, list[ApiCapability]] = {}
        for capability in self.capabilities:
            grouped.setdefault(capability.module_id, []).append(capability)
        for items in grouped.values():
            items.sort(
                key=lambda item: (
                    0 if item.provider_kind == "class" else 1,
                    item.provider_name,
                    item.kind,
                    item.display,
                    item.id,
                )
            )
        return grouped

    def role_info(self, provider_id: str) -> ProviderRoleInfo | None:
        return self.provider_roles.get(provider_id)
