"""Architecture bundle validation helpers."""

from __future__ import annotations

import re
from typing import Any

from ..config.contract_config import (
    API_EXPOSING_ROLES,
    CAPABILITY_KINDS,
    EXPOSURE_SOURCES,
    EXPOSURE_VALUES,
    PROTOCOL_CAPABILITY_KINDS,
    PROVIDER_ROLE_ORDER,
    PROVIDER_ROLE_SOURCES,
    PROVIDER_ROLES,
)
from ..config.project_config import MODULE_KINDS, MODULE_ROLES


def _issue(severity: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, **extra}


def _validate_capability(
    api: dict[str, Any],
    *,
    module_id: str,
    detail_by_id: dict[str, Any],
    class_ids: set[str],
    seen: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    api_id = api.get("id")
    if not api_id or api_id in seen:
        issues.append(_issue("error", "PROVIDED_API_DUPLICATE", f"module {module_id} has duplicate/missing provided API id"))
    seen.add(api_id)
    kind = api.get("kind")
    if kind not in CAPABILITY_KINDS:
        issues.append(_issue("error", "PROVIDED_API_KIND", f"module {module_id} provided API {api_id} has invalid kind: {kind}"))
    if api.get("exposure") not in EXPOSURE_VALUES:
        issues.append(_issue("error", "PROVIDED_API_EXPOSURE", f"module {module_id} provided API {api_id} has invalid exposure"))
    if api.get("exposureSource") not in EXPOSURE_SOURCES:
        issues.append(_issue("error", "PROVIDED_API_SOURCE", f"module {module_id} provided API {api_id} has invalid exposure source"))
    function_id = api.get("functionId")
    if function_id and function_id not in detail_by_id:
        issues.append(_issue("error", "PROVIDED_API_FUNCTION_MISSING", f"module {module_id} provided API references missing function {function_id}"))
    if api.get("providerKind") == "class" and api.get("providerId") not in class_ids:
        issues.append(_issue("error", "PROVIDED_API_OWNER_MISSING", f"module {module_id} provided API provider missing: {api.get('providerId')}"))
    for evidence_id in api.get("evidenceFunctionIds", []):
        if evidence_id and evidence_id not in detail_by_id:
            issues.append(_issue("error", "PROVIDED_API_EVIDENCE_MISSING", f"module {module_id} provided API evidence missing: {evidence_id}"))
    constructor_id = api.get("constructorFunctionId")
    if constructor_id and constructor_id not in detail_by_id:
        issues.append(_issue("error", "PROVIDED_API_CONSTRUCTOR_MISSING", f"module {module_id} provided API constructor missing: {constructor_id}"))
    role = api.get("providerRole")
    if role is not None and role not in PROVIDER_ROLES:
        issues.append(_issue("error", "PROVIDED_API_ROLE", f"module {module_id} provided API {api_id} has invalid providerRole: {role}"))
    source = api.get("roleSource")
    if source is not None and source not in PROVIDER_ROLE_SOURCES:
        issues.append(_issue("error", "PROVIDED_API_ROLE_SOURCE", f"module {module_id} provided API {api_id} has invalid roleSource: {source}"))
    visibility = api.get("providerVisibility")
    if visibility not in {"public", "internal"}:
        issues.append(_issue("error", "PROVIDED_API_VISIBILITY", f"module {module_id} provided API {api_id} has invalid providerVisibility: {visibility}"))
    provider_id = api.get("providerId")
    declared_in = api.get("declaredInProviderId")
    if declared_in and declared_in not in class_ids and declared_in.startswith("cls:"):
        issues.append(_issue("error", "PROVIDED_API_DECLARED_MISSING", f"module {module_id} provided API {api_id} references missing declaring provider {declared_in}"))
    if api.get("inherited"):
        if declared_in == provider_id:
            issues.append(_issue("error", "INHERITED_API_DECLARATION", f"module {module_id} inherited API {api_id} must preserve a base declaration"))
        inherited_from = api.get("inheritedFromProviderId")
        if inherited_from and inherited_from not in class_ids:
            issues.append(_issue("error", "INHERITED_API_SOURCE_MISSING", f"module {module_id} inherited API {api_id} references missing base provider {inherited_from}"))
    elif declared_in and declared_in != provider_id:
        issues.append(_issue("error", "DECLARED_API_OWNER", f"module {module_id} declared API {api_id} has mismatched declaring provider"))
    return issues


def _validate_provider_role_fields(
    item: dict[str, Any], *, label: str
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    role = item.get("providerRole")
    if role not in PROVIDER_ROLES:
        issues.append(_issue("error", "PROVIDER_ROLE", f"{label} has invalid/missing providerRole: {role}"))
    source = item.get("roleSource")
    if source not in PROVIDER_ROLE_SOURCES:
        issues.append(_issue("error", "PROVIDER_ROLE_SOURCE", f"{label} has invalid/missing roleSource: {source}"))
    if item.get("roleConfidence") not in {"high", "medium", "low"}:
        issues.append(_issue("error", "PROVIDER_ROLE_CONFIDENCE", f"{label} has invalid roleConfidence"))
    if item.get("providerVisibility") not in {"public", "internal"}:
        issues.append(_issue("error", "PROVIDER_VISIBILITY", f"{label} has invalid/missing providerVisibility"))
    return issues
def validate_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if bundle.get("kind") != "archmap.bundle":
        issues.append(_issue("error", "BUNDLE_KIND", "top-level kind must be archmap.bundle"))
    if str(bundle.get("schemaVersion")) != "3.8":
        issues.append(_issue("error", "SCHEMA_VERSION", "schemaVersion must be 3.8"))

    project_graph = bundle.get("projectGraph") or {}
    module_graphs = bundle.get("moduleGraphs") or []
    details = bundle.get("functionDetails") or []
    call_sites = bundle.get("callSites") or []
    detail_by_id = {detail.get("id"): detail for detail in details}
    if len(detail_by_id) != len(details):
        issues.append(_issue("error", "DUPLICATE_FUNCTION", "duplicate function detail ids"))

    module_ids = {module.get("id") for module in project_graph.get("modules", [])}
    if len(module_ids) != len(project_graph.get("modules", [])):
        issues.append(_issue("error", "DUPLICATE_MODULE", "duplicate module ids"))
    capability_by_id: dict[str, tuple[str, dict[str, Any]]] = {
        str(api.get("id")): (str(graph.get("moduleId")), api)
        for graph in module_graphs
        for api in graph.get("providedApis", [])
    }
    main_module_id = project_graph.get("mainModuleId")
    if main_module_id not in module_ids:
        issues.append(_issue("error", "MAIN_MODULE_MISSING", f"mainModuleId must reference a module: {main_module_id}"))
    main_modules = [
        module for module in project_graph.get("modules", [])
        if module.get("moduleKind") == "main"
    ]
    if len(main_modules) != 1:
        issues.append(_issue("error", "MAIN_MODULE_COUNT", f"project must contain exactly one main module, got {len(main_modules)}"))
    if main_modules and main_modules[0].get("id") != main_module_id:
        issues.append(_issue("error", "MAIN_MODULE_MISMATCH", "mainModuleId does not match the module marked as main"))
    if "boundaryNodes" in project_graph:
        issues.append(_issue("error", "PROJECT_BOUNDARY_REMOVED", "projectGraph.boundaryNodes is no longer supported"))
    if "inputs" in (project_graph.get("project") or {}) or "outputs" in (project_graph.get("project") or {}):
        issues.append(_issue("error", "PROJECT_IO_REMOVED", "projectGraph.project must not define module-style inputs/outputs"))

    class_ids: set[str] = {
        node.get("id")
        for graph in module_graphs
        for node in graph.get("nodes", [])
        if node.get("kind") == "class"
    }
    seen_class_ids: set[str] = set()
    module_graph_by_id = {graph.get("moduleId"): graph for graph in module_graphs}
    for graph in module_graphs:
        module_id = graph.get("moduleId")
        role = graph.get("role")
        if role is not None and role not in MODULE_ROLES:
            issues.append(_issue("error", "MODULE_ROLE", f"module {module_id} has invalid role: {role}"))
        if graph.get("moduleKind") not in MODULE_KINDS:
            issues.append(_issue("error", "MODULE_KIND", f"module {module_id} has invalid moduleKind: {graph.get('moduleKind')}"))
        if "inputs" in graph or "outputs" in graph:
            issues.append(_issue("error", "MODULE_IO_REMOVED", f"module {module_id} must not define inputs/outputs"))
        for node in graph.get("nodes", []):
            if node.get("kind") in {"input", "output"}:
                issues.append(_issue("error", "MODULE_BOUNDARY_NODE", f"module {module_id} contains removed boundary node {node.get('id')}"))
        node_role_by_id: dict[str, str] = {}
        for node in graph.get("nodes", []):
            if node.get("kind") not in {"class", "function"}:
                continue
            issues.extend(
                _validate_provider_role_fields(
                    node, label=f"module {module_id} provider {node.get('id')}"
                )
            )
            node_role_by_id[node.get("id")] = str(node.get("providerRole") or "")
            if node.get("providerRole") in {"config", "model"}:
                if node.get("providedApis"):
                    issues.append(_issue("error", "ROLE_API_LEAK", f"module {module_id} config/model provider {node.get('id')} exposes module APIs"))
                if not isinstance(node.get("typeSummary"), dict):
                    issues.append(_issue("error", "TYPE_SUMMARY_MISSING", f"module {module_id} config/model provider {node.get('id')} has no typeSummary"))
            if node.get("providerRole") == "utility" and node.get("providedApis"):
                issues.append(_issue("error", "UTILITY_API_LEAK", f"module {module_id} utility provider {node.get('id')} exposes module APIs"))
        composition = graph.get("moduleComposition") or {}
        if not isinstance(composition, dict):
            issues.append(_issue("error", "MODULE_COMPOSITION", f"module {module_id} moduleComposition must be an object"))
            composition = {}
        for role_name, provider_ids in composition.items():
            if role_name not in PROVIDER_ROLES:
                issues.append(_issue("error", "MODULE_COMPOSITION_ROLE", f"module {module_id} has invalid composition role: {role_name}"))
                continue
            if not isinstance(provider_ids, list):
                issues.append(_issue("error", "MODULE_COMPOSITION_IDS", f"module {module_id} composition {role_name} must be a list"))
                continue
            for provider_id in provider_ids:
                if provider_id not in node_role_by_id:
                    issues.append(_issue("error", "MODULE_COMPOSITION_PROVIDER", f"module {module_id} composition references missing provider: {provider_id}"))
                elif node_role_by_id.get(provider_id) != role_name:
                    issues.append(_issue("error", "MODULE_COMPOSITION_ROLE_MISMATCH", f"module {module_id} composition role disagrees for {provider_id}"))
        expected_composition_ids = {node_id for node_id in node_role_by_id}
        actual_composition_ids = {
            provider_id
            for provider_ids in composition.values()
            if isinstance(provider_ids, list)
            for provider_id in provider_ids
        }
        if expected_composition_ids != actual_composition_ids:
            issues.append(_issue("error", "MODULE_COMPOSITION_COVERAGE", f"module {module_id} moduleComposition does not cover exactly its providers"))
        public_composition = graph.get("publicModuleComposition")
        if not isinstance(public_composition, dict):
            issues.append(_issue("error", "PUBLIC_MODULE_COMPOSITION", f"module {module_id} publicModuleComposition must be an object"))
            public_composition = {}
        for role_name, provider_ids in public_composition.items():
            if role_name not in PROVIDER_ROLES or not isinstance(provider_ids, list):
                issues.append(_issue("error", "PUBLIC_MODULE_COMPOSITION", f"module {module_id} has invalid public composition"))
                continue
            for provider_id in provider_ids:
                if provider_id not in composition.get(role_name, []):
                    issues.append(_issue("error", "PUBLIC_MODULE_COMPOSITION_PROVIDER", f"module {module_id} public composition provider not in full composition: {provider_id}"))
                node = next((item for item in graph.get("nodes", []) if item.get("id") == provider_id), None)
                if node is None or node.get("providerVisibility") != "public":
                    issues.append(_issue("error", "PUBLIC_MODULE_COMPOSITION_VISIBILITY", f"module {module_id} public composition includes non-public provider: {provider_id}"))
        public_counts = graph.get("publicProviderRoleCounts")
        if not isinstance(public_counts, dict):
            issues.append(_issue("error", "PUBLIC_PROVIDER_ROLE_COUNTS", f"module {module_id} publicProviderRoleCounts must be an object"))
            public_counts = {}
        for role_name, provider_ids in public_composition.items():
            if public_counts.get(role_name) != len(provider_ids):
                issues.append(_issue("error", "PUBLIC_PROVIDER_ROLE_COUNT", f"module {module_id} publicProviderRoleCounts mismatch for {role_name}"))
        counts = graph.get("providerRoleCounts")
        if not isinstance(counts, dict):
            issues.append(_issue("error", "PROVIDER_ROLE_COUNTS", f"module {module_id} providerRoleCounts must be an object"))
            counts = {}
        for role_name in PROVIDER_ROLE_ORDER:
            actual = len(composition.get(role_name, [])) if isinstance(composition.get(role_name, []), list) else 0
            if counts.get(role_name) != actual:
                issues.append(_issue("error", "PROVIDER_ROLE_COUNT", f"module {module_id} providerRoleCounts mismatch for {role_name}"))
        seen_apis: set[str] = set()
        for api in graph.get("providedApis", []):
            issues.extend(
                _validate_capability(
                    api,
                    module_id=module_id,
                    detail_by_id=detail_by_id,
                    class_ids=class_ids,
                    seen=seen_apis,
                )
            )
        provider_apis: list[dict[str, Any]] = []
        for provider in graph.get("apiProviders", []):
            provider_id = provider.get("providerId")
            issues.extend(
                _validate_provider_role_fields(
                    provider, label=f"module {module_id} apiProvider {provider_id}"
                )
            )
            if provider_id in node_role_by_id and provider.get("providerRole") != node_role_by_id[provider_id]:
                issues.append(_issue("error", "API_PROVIDER_ROLE_MISMATCH", f"module {module_id} apiProvider role disagrees for {provider_id}"))
            if provider.get("providerRole") in {"config", "model", "utility"}:
                issues.append(_issue("error", "API_PROVIDER_ROLE_EXPOSED", f"module {module_id} apiProvider {provider_id} is non-behavioral role"))
            for api in provider.get("apis", []):
                provider_apis.append(api)
                issues.extend(
                    _validate_capability(
                        api,
                        module_id=module_id,
                        detail_by_id=detail_by_id,
                        class_ids=class_ids,
                        seen=set(),
                    )
                )
        if {api.get("id") for api in provider_apis} != {api.get("id") for api in graph.get("providedApis", [])}:
            issues.append(_issue("error", "PROVIDED_API_PROVIDER_MISMATCH", f"module {module_id} apiProviders and providedApis disagree"))
        for node in graph.get("nodes", []):
            if node.get("kind") == "class":
                if node.get("id") in seen_class_ids:
                    issues.append(_issue("error", "DUPLICATE_CLASS", f"duplicate class node: {node.get('id')}"))
                seen_class_ids.add(node.get("id"))
                usage = node.get("usage") or {}
                constructor = usage.get("constructor") or {}
                constructor_id = constructor.get("functionId")
                if constructor_id and constructor_id not in detail_by_id:
                    issues.append(_issue("error", "CLASS_CONSTRUCTOR_MISSING", f"class {node.get('id')} constructor missing: {constructor_id}"))
                class_api_ids: set[str] = set()
                for api in node.get("providedApis", []):
                    if api.get("providerId") != node.get("id"):
                        issues.append(_issue("error", "CLASS_API_PROVIDER", f"class {node.get('id')} provided API has wrong provider"))
                    class_api_ids.add(api.get("id"))
                if node.get("providedApiCount") != len(class_api_ids):
                    issues.append(_issue("error", "CLASS_API_COUNT", f"class {node.get('id')} providedApiCount mismatch"))
                for method in node.get("methods", []):
                    method_id = method.get("id")
                    if method.get("ownerClassId") != node.get("id"):
                        issues.append(_issue("error", "METHOD_OWNER", f"method {method_id} has wrong ownerClassId"))
                    detail = detail_by_id.get(method_id)
                    if detail is None:
                        issues.append(_issue("error", "METHOD_DETAIL_MISSING", f"class {node.get('id')} method {method_id} has no function detail"))
                    elif detail.get("ownerClassId") != node.get("id"):
                        issues.append(_issue("error", "METHOD_DETAIL_OWNER", f"function detail {method_id} has wrong ownerClassId"))

    # P3 structural type relations: endpoints must be canonical local classes,
    # directions are directed, and cycles are rejected rather than silently
    # rendered as a hierarchy.
    project_relations = project_graph.get("typeRelations")
    if project_relations is None:
        issues.append(_issue("error", "TYPE_RELATIONS_MISSING", "projectGraph.typeRelations must be an array"))
        project_relations = []
    relation_keys: set[tuple[str, str, str]] = set()
    graph_by_class: dict[str, list[str]] = {cid: [] for cid in class_ids}
    module_relation_keys: set[tuple[str, str, str, str]] = set()
    for graph in module_graphs:
        for relation in graph.get("typeRelations", []):
            key = (
                str(relation.get("fromClassId")),
                str(relation.get("kind")),
                str(relation.get("toClassId")),
                str(graph.get("moduleId")),
            )
            if key in module_relation_keys:
                issues.append(_issue("error", "TYPE_RELATION_DUPLICATE", f"module {graph.get('moduleId')} has duplicate type relation {key}"))
            module_relation_keys.add(key)
    for relation in project_relations:
        relation_id = relation.get("id")
        from_id = relation.get("fromClassId")
        to_id = relation.get("toClassId")
        kind = relation.get("kind")
        if kind not in {"inherits", "implements", "instantiates", "uses", "aggregates", "composes"}:
            issues.append(_issue("error", "TYPE_RELATION_KIND", f"type relation {relation_id} has invalid kind: {kind}"))
        for role_field in ("fromProviderRole", "toProviderRole"):
            value = relation.get(role_field)
            if value is not None and value not in PROVIDER_ROLES:
                issues.append(_issue("error", "TYPE_RELATION_ROLE", f"type relation {relation_id} has invalid {role_field}: {value}"))
        if from_id not in class_ids or to_id not in class_ids:
            issues.append(_issue("error", "TYPE_RELATION_ENDPOINT", f"type relation {relation_id} has missing class endpoint"))
            continue
        if from_id == to_id:
            issues.append(_issue("error", "TYPE_RELATION_SELF", f"type relation {relation_id} cannot be self-referential"))
        key = (str(from_id), str(kind), str(to_id))
        if key in relation_keys:
            issues.append(_issue("error", "TYPE_RELATION_DUPLICATE", f"duplicate type relation {key}"))
        relation_keys.add(key)
        graph_by_class.setdefault(str(from_id), []).append(str(to_id))
        if relation.get("confidence") not in {"high", "medium", "low"}:
            issues.append(_issue("error", "TYPE_RELATION_CONFIDENCE", f"type relation {relation_id} has invalid confidence"))

    def _has_cycle(start: str, current: str, path: set[str]) -> bool:
        if current in path:
            return True
        for target in graph_by_class.get(current, []):
            if target == start or _has_cycle(start, target, {*path, current}):
                return True
        return False

    for cid in graph_by_class:
        if _has_cycle(cid, cid, set()):
            issues.append(_issue("error", "TYPE_RELATION_CYCLE", f"type hierarchy contains a cycle involving {cid}"))
            break

    relation_module_tuples = {
        (str(relation.get("fromClassId")), str(relation.get("kind")), str(relation.get("toClassId")), str(relation.get("moduleId")))
        for relation in project_relations
    }
    if module_relation_keys != relation_module_tuples:
        issues.append(_issue("error", "TYPE_RELATION_MODULE_MISMATCH", "module typeRelations do not match projectGraph.typeRelations"))

    for graph in module_graphs:
        for node in graph.get("nodes", []):
            if node.get("kind") != "class":
                continue
            for base_id in node.get("baseClassIds", []):
                if base_id not in class_ids:
                    issues.append(_issue("error", "CLASS_BASE_MISSING", f"class {node.get('id')} references missing base {base_id}"))
            for subclass_id in node.get("subclassIds", []):
                if subclass_id not in class_ids:
                    issues.append(_issue("error", "CLASS_SUBCLASS_MISSING", f"class {node.get('id')} references missing subclass {subclass_id}"))
            if node.get("declaredApiCount", 0) + node.get("inheritedApiCount", 0) != node.get("providedApiCount", 0):
                issues.append(_issue("error", "CLASS_API_COUNTS", f"class {node.get('id')} declared/inherited API counts do not sum to providedApiCount"))

    surfaces = project_graph.get("userSurfaces", [])
    if not isinstance(surfaces, list):
        issues.append(_issue("error", "USER_SURFACES", "projectGraph.userSurfaces must be an array"))
        surfaces = []
    surface_ids: set[str] = set()
    valid_surface_kinds = {
        "cli_input", "cli_output", "file_io", "network_endpoint",
        "network_client", "keyboard_event", "http_endpoint",
        "tui_menu", "ui_component",
    }
    for surface in surfaces:
        surface_id = str(surface.get("id") or "")
        if not surface_id or surface_id in surface_ids:
            issues.append(_issue("error", "USER_SURFACE_ID", "user surface has missing/duplicate id"))
        surface_ids.add(surface_id)
        if surface.get("kind") not in valid_surface_kinds:
            issues.append(_issue("error", "USER_SURFACE_KIND", f"user surface {surface_id} has invalid kind: {surface.get('kind')}"))
        if surface.get("confidence") not in {"high", "medium", "low"}:
            issues.append(_issue("error", "USER_SURFACE_CONFIDENCE", f"user surface {surface_id} has invalid confidence"))
        module_id = surface.get("moduleId")
        if module_id not in module_ids:
            issues.append(_issue("error", "USER_SURFACE_MODULE", f"user surface {surface_id} references missing module {module_id}"))
        for function_id in surface.get("evidenceFunctionIds", []):
            if function_id not in detail_by_id:
                issues.append(_issue("error", "USER_SURFACE_EVIDENCE", f"user surface {surface_id} references missing evidence function {function_id}"))
        for entrypoint_id in surface.get("entrypointIds", []):
            if entrypoint_id not in detail_by_id:
                issues.append(_issue("error", "USER_SURFACE_ENTRYPOINT", f"user surface {surface_id} references missing entrypoint {entrypoint_id}"))
    module_surface_ids: set[str] = set()
    for graph in module_graphs:
        if not isinstance(graph.get("userSurfaces"), list):
            issues.append(_issue("error", "MODULE_USER_SURFACES", f"module {graph.get('moduleId')} userSurfaces must be an array"))
            continue
        for surface in graph.get("userSurfaces", []):
            surface_id = str(surface.get("id") or "")
            module_surface_ids.add(surface_id)
            if surface_id not in surface_ids:
                issues.append(_issue("error", "MODULE_USER_SURFACE_MISSING", f"module {graph.get('moduleId')} has unknown user surface {surface_id}"))
            if surface.get("moduleId") != graph.get("moduleId"):
                issues.append(_issue("error", "MODULE_USER_SURFACE_MODULE", f"module {graph.get('moduleId')} surface has wrong moduleId"))
    if surface_ids != module_surface_ids:
        issues.append(_issue("error", "USER_SURFACE_PROJECT_MISMATCH", "module userSurfaces do not match projectGraph.userSurfaces"))

    for entry in bundle.get("entrypoints", []):
        if entry.get("functionId") not in detail_by_id:
            issues.append(_issue("error", "ENTRYPOINT_MISSING", f"entrypoint function missing: {entry.get('functionId')}"))

    for module in project_graph.get("modules", []):
        role = module.get("role")
        if role is not None and role not in MODULE_ROLES:
            issues.append(_issue("error", "MODULE_ROLE", f"project module {module.get('id')} has invalid role: {role}"))
        if module.get("moduleKind") not in MODULE_KINDS:
            issues.append(_issue("error", "PROJECT_MODULE_KIND", f"project module {module.get('id')} has invalid moduleKind: {module.get('moduleKind')}"))
        if "inputs" in module or "outputs" in module:
            issues.append(_issue("error", "PROJECT_MODULE_IO_REMOVED", f"project module {module.get('id')} must not define inputs/outputs"))
        graph = module_graph_by_id.get(module.get("id"))
        if graph is not None and module.get("providedApiCount") != len(graph.get("providedApis", [])):
            issues.append(_issue("error", "PROVIDED_API_COUNT", f"project module {module.get('id')} providedApiCount does not match module graph"))
        if graph is not None:
            if module.get("moduleComposition") != graph.get("moduleComposition"):
                issues.append(_issue("error", "PROJECT_MODULE_COMPOSITION", f"project module {module.get('id')} composition does not match module graph"))
            if module.get("providerRoleCounts") != graph.get("providerRoleCounts"):
                issues.append(_issue("error", "PROJECT_PROVIDER_ROLE_COUNT", f"project module {module.get('id')} providerRoleCounts does not match module graph"))
            if module.get("publicModuleComposition") != graph.get("publicModuleComposition"):
                issues.append(_issue("error", "PROJECT_PUBLIC_COMPOSITION", f"project module {module.get('id')} publicModuleComposition does not match module graph"))
            if module.get("publicProviderRoleCounts") != graph.get("publicProviderRoleCounts"):
                issues.append(_issue("error", "PROJECT_PUBLIC_ROLE_COUNT", f"project module {module.get('id')} publicProviderRoleCounts does not match module graph"))
        for fn_id in module.get("functions", []):
            if fn_id not in detail_by_id:
                issues.append(_issue("error", "MODULE_FUNCTION_MISSING", f"module {module.get('id')} references missing function {fn_id}"))
        for class_id in module.get("classes", []):
            if class_id not in class_ids:
                issues.append(_issue("error", "MODULE_CLASS_MISSING", f"module {module.get('id')} references missing class {class_id}"))

    for edge in project_graph.get("edges", []):
        if edge.get("from") not in module_ids or edge.get("to") not in module_ids:
            issues.append(_issue("error", "PROJECT_EDGE_ENDPOINT", f"project edge endpoint missing: {edge.get('id')}"))
        if edge.get("role") != "internal":
            issues.append(_issue("error", "PROJECT_EDGE_ROLE", f"project edge {edge.get('id')} must use role=internal"))

    flows = project_graph.get("mainFlows")
    if not isinstance(flows, list):
        issues.append(_issue("error", "MAIN_FLOWS", "projectGraph.mainFlows must be an array"))
        flows = []
    flow_ids = {flow.get("id") for flow in flows}
    primary_flow_id = project_graph.get("primaryFlowId")
    if primary_flow_id is not None and primary_flow_id not in flow_ids:
        issues.append(_issue("error", "PRIMARY_FLOW_MISSING", f"primaryFlowId does not reference a main flow: {primary_flow_id}"))
    if flows and primary_flow_id is None:
        issues.append(_issue("error", "PRIMARY_FLOW_MISSING", "primaryFlowId is required when mainFlows is non-empty"))
    for flow in flows:
        flow_id = flow.get("id")
        flow_node_ids = {node.get("id") for node in flow.get("nodes", [])}
        if len(flow_node_ids) != len(flow.get("nodes", [])):
            issues.append(_issue("error", "FLOW_NODE_DUPLICATE", f"flow {flow_id} has duplicate node ids"))
        entry_nodes = [node for node in flow.get("nodes", []) if node.get("isEntry") or node.get("kind") == "entry"]
        if len(entry_nodes) != 1:
            issues.append(_issue("error", "FLOW_ENTRY_COUNT", f"flow {flow_id} must contain exactly one entry node"))
        elif entry_nodes[0].get("functionId") != flow.get("entrypointId"):
            issues.append(_issue("error", "FLOW_ENTRY_MISMATCH", f"flow {flow_id} entry node does not match entrypointId"))
        for node in flow.get("nodes", []):
            function_id = node.get("functionId")
            if function_id and function_id not in detail_by_id:
                issues.append(_issue("error", "FLOW_FUNCTION_MISSING", f"flow {flow_id} node references missing function {function_id}"))
            node_module_id = node.get("moduleId")
            if node_module_id and node_module_id not in module_ids:
                issues.append(_issue("error", "FLOW_MODULE_MISSING", f"flow {flow_id} node references missing module {node_module_id}"))
            if node.get("kind") == "dispatch":
                if not isinstance(node.get("candidateCount"), int) or node.get("candidateCount") < 0:
                    issues.append(_issue("error", "DISPATCH_CANDIDATES", f"flow {flow_id} dispatch node has invalid candidateCount"))
                if not isinstance(node.get("candidateSetComplete"), bool):
                    issues.append(_issue("error", "DISPATCH_COMPLETE", f"flow {flow_id} dispatch node must define candidateSetComplete"))
            if node.get("kind") == "interface":
                capability_id = str(node.get("capabilityId") or "")
                capability = capability_by_id.get(capability_id)
                if capability is None:
                    issues.append(_issue("error", "FLOW_INTERFACE_NOT_CANONICAL", f"flow {flow_id} interface {node.get('id')} does not reference a canonical provided API"))
                else:
                    capability_module_id, capability_payload = capability
                    if capability_module_id != node.get("moduleId"):
                        issues.append(_issue("error", "FLOW_INTERFACE_MODULE", f"flow {flow_id} interface {node.get('id')} module disagrees with its capability"))
                    if capability_payload.get("providerRole") in {"config", "model", "utility"}:
                        issues.append(_issue("error", "FLOW_INTERFACE_ROLE", f"flow {flow_id} interface {node.get('id')} references a non-behavioral capability"))
            if node.get("kind") == "provider" and node.get("capabilityId"):
                capability_id = str(node.get("capabilityId"))
                capability = capability_by_id.get(capability_id)
                if capability is None:
                    issues.append(_issue("error", "FLOW_PROVIDER_CAPABILITY_NOT_CANONICAL", f"flow {flow_id} provider {node.get('id')} references a missing capability"))
                else:
                    capability_module_id, capability_payload = capability
                    if capability_module_id != node.get("moduleId"):
                        issues.append(_issue("error", "FLOW_PROVIDER_CAPABILITY_MODULE", f"flow {flow_id} provider {node.get('id')} module disagrees with its capability"))
                    if capability_payload.get("providerId") != node.get("providerId"):
                        issues.append(_issue("error", "FLOW_PROVIDER_CAPABILITY_OWNER", f"flow {flow_id} provider {node.get('id')} does not own its capability"))
                    if capability_payload.get("kind") not in PROTOCOL_CAPABILITY_KINDS:
                        issues.append(_issue("error", "FLOW_PROVIDER_CAPABILITY_KIND", f"flow {flow_id} provider {node.get('id')} capability must be a protocol capability"))
            if node.get("flowBoundary"):
                if node.get("moduleId") == main_module_id:
                    issues.append(_issue("error", "FLOW_BOUNDARY_MAIN", f"flow {flow_id} main-module node {node.get('id')} cannot be a boundary"))
                if node.get("kind") not in {"interface", "provider"}:
                    issues.append(_issue("error", "FLOW_BOUNDARY_KIND", f"flow {flow_id} boundary node {node.get('id')} must be interface/provider"))
                if node.get("expandable") is not False:
                    issues.append(_issue("error", "FLOW_BOUNDARY_EXPANDABLE", f"flow {flow_id} boundary node {node.get('id')} must not be expandable"))
        composition_by_source: dict[str, int] = {}
        outgoing_sources: set[str] = set()
        for edge in flow.get("edges", []):
            if edge.get("from") not in flow_node_ids or edge.get("to") not in flow_node_ids:
                issues.append(_issue("error", "FLOW_EDGE_ENDPOINT", f"flow {flow_id} edge endpoint missing: {edge.get('id')}"))
            kind = edge.get("kind")
            if kind not in {"call", "call_path", "composition"}:
                issues.append(_issue("error", "FLOW_EDGE_KIND", f"flow {flow_id} edge {edge.get('id')} has invalid kind: {kind}"))
            if kind == "composition" and edge.get("confidence") != "low":
                issues.append(_issue("error", "FLOW_COMPOSITION_CONFIDENCE", f"flow {flow_id} composition edge {edge.get('id')} must be low confidence"))
            outgoing_sources.add(str(edge.get("from")))
            if kind == "composition":
                source = str(edge.get("from"))
                composition_by_source[source] = composition_by_source.get(source, 0) + 1
        for node in flow.get("nodes", []):
            if node.get("flowBoundary") and node.get("id") in outgoing_sources:
                issues.append(_issue("error", "FLOW_BOUNDARY_OUTGOING", f"flow {flow_id} boundary node {node.get('id')} must not have outgoing flow edges"))
        for node in flow.get("nodes", []):
            if node.get("kind") != "dispatch":
                continue
            actual = composition_by_source.get(str(node.get("id")), 0)
            expected = int(node.get("candidateCount") or 0)
            if actual != expected:
                issues.append(_issue("error", "DISPATCH_CANDIDATE_EDGE_COUNT", f"flow {flow_id} dispatch node {node.get('id')} has {actual} composition edges, expected {expected}"))

    for graph in module_graphs:
        module_id = graph.get("moduleId")
        node_ids = {node.get("id") for node in graph.get("nodes", [])}
        for node in graph.get("nodes", []):
            if node.get("kind") == "function" and node.get("functionDetailId") not in detail_by_id:
                issues.append(_issue("error", "FUNCTION_DETAIL_MISSING", f"module {module_id} references missing function detail {node.get('functionDetailId')}"))
        for edge in graph.get("edges", []):
            if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
                issues.append(_issue("error", "MODULE_EDGE_ENDPOINT", f"module {module_id} edge endpoint missing: {edge.get('id')}"))
        for edge in graph.get("methodEdges", []):
            for endpoint in (edge.get("from"), edge.get("to")):
                if endpoint not in detail_by_id:
                    issues.append(_issue("error", "METHOD_EDGE_ENDPOINT", f"module {module_id} method edge endpoint missing: {endpoint}"))

    for detail in details:
        detail_id = detail.get("id")
        for field in ("name", "qualifiedName", "moduleId", "file", "line", "endLine", "signature", "sourceHash"):
            if field not in detail:
                issues.append(_issue("error", "DETAIL_FIELD", f"{detail_id}: missing {field}"))
        source = detail.get("source") or {}
        for field in ("text", "startLine", "endLine"):
            if field not in source:
                issues.append(_issue("error", "SOURCE_FIELD", f"{detail_id}: source missing {field}"))
        source_hash = str(detail.get("sourceHash") or "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", source_hash):
            issues.append(_issue("error", "SOURCE_HASH", f"{detail_id}: invalid sourceHash"))
        if detail.get("apiExposure") not in EXPOSURE_VALUES:
            issues.append(_issue("error", "DETAIL_EXPOSURE", f"{detail_id}: invalid apiExposure"))
        if detail.get("apiExposureSource") not in EXPOSURE_SOURCES:
            issues.append(_issue("error", "DETAIL_EXPOSURE_SOURCE", f"{detail_id}: invalid apiExposureSource"))
        owner_class_id = detail.get("ownerClassId")
        if owner_class_id and owner_class_id not in class_ids:
            issues.append(_issue("error", "OWNER_CLASS_MISSING", f"{detail_id}: owner class missing {owner_class_id}"))
        for caller in detail.get("callers", []):
            if caller.get("functionId") not in detail_by_id:
                issues.append(_issue("error", "CALLER_MISSING", f"{detail_id}: caller missing {caller.get('functionId')}"))
        for callee in detail.get("callees", []):
            target = callee.get("functionId")
            if target and target not in detail_by_id:
                issues.append(_issue("error", "CALLEE_MISSING", f"{detail_id}: callee missing {target}"))

    for site in call_sites:
        from_id = site.get("fromFunctionId")
        to_id = site.get("toFunctionId")
        if from_id not in detail_by_id:
            issues.append(_issue("error", "CALL_FROM_MISSING", f"call site {site.get('id')} from function missing: {from_id}"))
        if site.get("resolved") and to_id not in detail_by_id:
            issues.append(_issue("error", "CALL_TO_MISSING", f"call site {site.get('id')} resolved target missing: {to_id}"))
        if not site.get("resolved") and to_id:
            issues.append(_issue("warning", "CALL_UNRESOLVED_TARGET", f"call site {site.get('id')} is unresolved but has a target"))
        if not isinstance(site.get("line"), int) or int(site.get("line", 0)) < 1:
            issues.append(_issue("error", "CALL_LINE", f"call site {site.get('id')} has invalid line"))
        if site.get("polymorphic"):
            candidates = site.get("candidates") or []
            if site.get("resolved") or site.get("toFunctionId"):
                issues.append(_issue("error", "POLYMORPHIC_CALL_RESOLVED", f"polymorphic call site {site.get('id')} must not claim one resolved target"))
            if not candidates:
                issues.append(_issue("error", "POLYMORPHIC_CALL_CANDIDATES", f"polymorphic call site {site.get('id')} has no candidates"))
            for candidate in candidates:
                if candidate not in detail_by_id:
                    issues.append(_issue("error", "POLYMORPHIC_CANDIDATE_MISSING", f"polymorphic call site {site.get('id')} candidate missing: {candidate}"))
        usage_kind = site.get("usageKind")
        if usage_kind is not None and usage_kind not in {"call", "instantiate", "context_manager", "async_context_manager"}:
            issues.append(_issue("error", "CALL_USAGE_KIND", f"call site {site.get('id')} has invalid usageKind: {usage_kind}"))
    return issues
