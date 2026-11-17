"""Language-neutral provider and capability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClassRelation:
    """A resolved structural type relationship between two local classes."""

    id: str
    kind: str
    from_class_id: str
    to_class_id: str
    to_class_name: str
    module_id: str
    target_module_id: str
    confidence: str = "high"
    evidence_file: str = ""
    evidence_line: int = 0
    from_provider_id: str | None = None
    to_provider_id: str | None = None
    source: str = "base_class"
    from_provider_role: str | None = None
    to_provider_role: str | None = None
    from_visibility: str | None = None
    to_visibility: str | None = None
    evidence_function_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "fromClassId": self.from_class_id,
            "toClassId": self.to_class_id,
            "toClassName": self.to_class_name,
            "fromProviderId": self.from_provider_id or self.from_class_id,
            "toProviderId": self.to_provider_id or self.to_class_id,
            "moduleId": self.module_id,
            "targetModuleId": self.target_module_id,
            "confidence": self.confidence,
            "source": self.source,
            "fromProviderRole": self.from_provider_role,
            "toProviderRole": self.to_provider_role,
            "fromVisibility": self.from_visibility,
            "toVisibility": self.to_visibility,
            "evidenceFunctionIds": list(self.evidence_function_ids),
            "evidence": {
                "file": self.evidence_file,
                "line": self.evidence_line,
            },
        }


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
    base_class_ids: list[str] = field(default_factory=list)
    subclass_ids: list[str] = field(default_factory=list)
    mro_class_ids: list[str] = field(default_factory=list)
    abstract_method_names: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "providerRole": self.role,
            "roleSource": self.role_source,
            "roleConfidence": self.role_confidence,
            "providerVisibility": self.provider_visibility,
            "ownerProviderId": self.owner_provider_id,
            "typeSummary": self.type_summary,
            "baseClassIds": list(self.base_class_ids),
            "subclassIds": list(self.subclass_ids),
            "mroClassIds": list(self.mro_class_ids),
            "abstractMethodNames": list(self.abstract_method_names),
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
    inherited: bool = False
    declared_in_provider_id: str | None = None
    inherited_from_provider_id: str | None = None
    overrides_capability_id: str | None = None
    inherited_from_class_ids: list[str] = field(default_factory=list)

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
            "inherited": self.inherited,
            "declaredInProviderId": self.declared_in_provider_id or self.provider_id,
            "inheritedFromProviderId": self.inherited_from_provider_id,
            "overridesCapabilityId": self.overrides_capability_id,
            "inheritedFromClassIds": list(self.inherited_from_class_ids),
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
    base_class_ids: list[str] = field(default_factory=list)
    subclass_ids: list[str] = field(default_factory=list)
    mro_class_ids: list[str] = field(default_factory=list)
    abstract_method_names: list[str] = field(default_factory=list)

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
            "baseClassIds": list(self.base_class_ids),
            "subclassIds": list(self.subclass_ids),
            "mroClassIds": list(self.mro_class_ids),
            "abstractMethodNames": list(self.abstract_method_names),
        }


@dataclass
class ContractModel:
    """Frontend-owned contract projection consumed by the neutral graph layer."""

    capabilities: list[ApiCapability] = field(default_factory=list)
    class_usage: dict[str, ClassUsage] = field(default_factory=dict)
    provider_roles: dict[str, ProviderRoleInfo] = field(default_factory=dict)
    class_relations: list[ClassRelation] = field(default_factory=list)

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
