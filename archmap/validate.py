from __future__ import annotations

import re
from typing import Any

from .config import MODULE_ROLES
from .contracts import CAPABILITY_KINDS, EXPOSURE_SOURCES, EXPOSURE_VALUES


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
    return issues


def validate_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if bundle.get("kind") != "archmap.bundle":
        issues.append(_issue("error", "BUNDLE_KIND", "top-level kind must be archmap.bundle"))
    if str(bundle.get("schemaVersion")) != "3.2":
        issues.append(_issue("error", "SCHEMA_VERSION", "schemaVersion must be 3.2"))

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

    for entry in bundle.get("entrypoints", []):
        if entry.get("functionId") not in detail_by_id:
            issues.append(_issue("error", "ENTRYPOINT_MISSING", f"entrypoint function missing: {entry.get('functionId')}"))

    for module in project_graph.get("modules", []):
        role = module.get("role")
        if role is not None and role not in MODULE_ROLES:
            issues.append(_issue("error", "MODULE_ROLE", f"project module {module.get('id')} has invalid role: {role}"))
        graph = module_graph_by_id.get(module.get("id"))
        if graph is not None and module.get("providedApiCount") != len(graph.get("providedApis", [])):
            issues.append(_issue("error", "PROVIDED_API_COUNT", f"project module {module.get('id')} providedApiCount does not match module graph"))
        for fn_id in module.get("functions", []):
            if fn_id not in detail_by_id:
                issues.append(_issue("error", "MODULE_FUNCTION_MISSING", f"module {module.get('id')} references missing function {fn_id}"))
        for class_id in module.get("classes", []):
            if class_id not in class_ids:
                issues.append(_issue("error", "MODULE_CLASS_MISSING", f"module {module.get('id')} references missing class {class_id}"))

    project_node_ids = {node.get("id") for node in project_graph.get("boundaryNodes", [])} | module_ids
    for edge in project_graph.get("edges", []):
        if edge.get("from") not in project_node_ids or edge.get("to") not in project_node_ids:
            issues.append(_issue("error", "PROJECT_EDGE_ENDPOINT", f"project edge endpoint missing: {edge.get('id')}"))

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
    return issues
