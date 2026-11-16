from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any


def _issue(severity: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message, **extra}


def _reachable(start: str, edges: list[dict[str, Any]], reverse: bool = False) -> set[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("type") != "next_step":
            continue
        src = edge["to"] if reverse else edge["from"]
        dst = edge["from"] if reverse else edge["to"]
        adjacency[src].add(dst)
    seen = {start}
    stack = [start]
    while stack:
        current = stack.pop()
        for nxt in adjacency.get(current, set()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _parse_path(d: str) -> list[tuple[str, list[float]]]:
    result: list[tuple[str, list[float]]] = []
    for match in re.finditer(r"([MLQ])\s+([^MLQ]+)", d):
        command = match.group(1)
        numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", match.group(2))]
        result.append((command, numbers))
    return result


def _check_path(d: str) -> list[str]:
    errors: list[str] = []
    if not d or not d.strip():
        return ["empty path"]
    if any(ch not in "MLQ0123456789.- " for ch in d):
        errors.append("path contains unsupported command")
    current: tuple[float, float] | None = None
    for command, numbers in _parse_path(d):
        if command == "M":
            if len(numbers) < 2:
                errors.append("invalid M")
                continue
            current = (numbers[0], numbers[1])
        elif command == "L":
            if len(numbers) < 2 or current is None:
                errors.append("invalid L")
                continue
            endpoint = (numbers[0], numbers[1])
            if abs(current[0] - endpoint[0]) > 0.01 and abs(current[1] - endpoint[1]) > 0.01:
                errors.append("non-orthogonal L segment")
            current = endpoint
        elif command == "Q":
            if len(numbers) < 4 or current is None:
                errors.append("invalid Q")
                continue
            current = (numbers[2], numbers[3])
    return errors


def _validate_function(flow: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    function_id = flow.get("id", "<unknown>")
    nodes = {node["id"]: node for node in flow.get("nodes", [])}
    edges = flow.get("edges", [])
    if not nodes:
        return [_issue("error", "EMPTY_FUNCTION", f"{function_id}: no nodes", functionId=function_id)]
    entries = [node for node in nodes.values() if node.get("type") == "entry"]
    exits = [node for node in nodes.values() if node.get("type") == "exit"]
    if len(entries) != 1:
        issues.append(_issue("error", "ENTRY_COUNT", f"{function_id}: expected one ENTRY, got {len(entries)}", functionId=function_id))
    if len(exits) != 1:
        issues.append(_issue("error", "EXIT_COUNT", f"{function_id}: expected one EXIT, got {len(exits)}", functionId=function_id))
    if len(entries) != 1 or len(exits) != 1:
        return issues
    entry_id, exit_id = entries[0]["id"], exits[0]["id"]
    control_edges = [edge for edge in edges if edge.get("type") == "next_step"]
    data_edges = [edge for edge in edges if edge.get("type") == "data_dep"]
    if len(control_edges) + len(data_edges) != len(edges):
        issues.append(_issue("error", "EDGE_TYPE", f"{function_id}: unsupported edge type", functionId=function_id))
    in_degree = Counter(edge["to"] for edge in control_edges)
    out_degree = Counter(edge["from"] for edge in control_edges)
    if in_degree.get(entry_id):
        issues.append(_issue("error", "ENTRY_INDEGREE", f"{function_id}: ENTRY has incoming edge", functionId=function_id))
    if out_degree.get(exit_id):
        issues.append(_issue("error", "EXIT_OUTDEGREE", f"{function_id}: EXIT has outgoing edge", functionId=function_id))
    reachable = _reachable(entry_id, control_edges)
    can_exit = _reachable(exit_id, control_edges, reverse=True)
    for node_id in sorted(nodes):
        if node_id not in reachable:
            issues.append(_issue("error", "UNREACHABLE_NODE", f"{function_id}: node {node_id} unreachable", functionId=function_id, nodeId=node_id))
        if node_id not in can_exit:
            issues.append(_issue("error", "NO_EXIT_PATH", f"{function_id}: node {node_id} cannot reach EXIT", functionId=function_id, nodeId=node_id))
    for edge in control_edges:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            issues.append(_issue("error", "EDGE_ENDPOINT", f"{function_id}: edge endpoint missing", functionId=function_id))
    for edge in data_edges:
        for endpoint in (edge["from"], edge["to"]):
            node = nodes.get(endpoint)
            if not node:
                issues.append(_issue("error", "DATA_ENDPOINT", f"{function_id}: data edge endpoint missing", functionId=function_id, nodeId=endpoint))
            elif node["type"] in {"entry", "exit", "merge"}:
                issues.append(_issue("error", "DATA_FORBIDDEN_ENDPOINT", f"{function_id}: data edge points to synthetic node", functionId=function_id, nodeId=endpoint))
    for node in nodes.values():
        node_type = node.get("type")
        if node_type == "branch":
            outgoing = [edge for edge in control_edges if edge["from"] == node["id"]]
            flows = Counter(edge.get("flow") for edge in outgoing)
            if flows.get("true") != 1 or flows.get("false") != 1:
                issues.append(_issue("error", "BRANCH_FLOW", f"{function_id}: branch must have one true and one false edge", functionId=function_id, nodeId=node["id"]))
        if node_type == "merge":
            incoming = [edge for edge in control_edges if edge["to"] == node["id"]]
            outgoing = [edge for edge in control_edges if edge["from"] == node["id"]]
            if len(incoming) < 2:
                issues.append(_issue("error", "MERGE_INCOMING", f"{function_id}: merge needs at least two incoming edges", functionId=function_id, nodeId=node["id"]))
            if len(outgoing) != 1:
                issues.append(_issue("error", "MERGE_OUTGOING", f"{function_id}: merge needs exactly one outgoing edge", functionId=function_id, nodeId=node["id"]))
            if node.get("mergeOf") not in nodes:
                issues.append(_issue("error", "MERGE_OWNER", f"{function_id}: mergeOf target missing", functionId=function_id, nodeId=node["id"]))
        if not node.get("synthetic"):
            for field in ("file", "line", "endLine"):
                if field not in node:
                    issues.append(_issue("error", "EVIDENCE", f"{function_id}: node {node['id']} missing {field}", functionId=function_id, nodeId=node["id"]))
    layout = flow.get("layout") or {}
    layout_nodes = layout.get("nodes") or {}
    canvas = layout.get("canvas") or {}
    if not layout_nodes:
        issues.append(_issue("error", "LAYOUT_MISSING", f"{function_id}: layout missing", functionId=function_id))
    else:
        rects: list[tuple[str, dict[str, Any]]] = []
        for node_id, rect in layout_nodes.items():
            rects.append((node_id, rect))
            if rect.get("x", 0) < -0.5 or rect.get("y", 0) < -0.5:
                issues.append(_issue("error", "LAYOUT_BOUNDS", f"{function_id}: node outside negative canvas", functionId=function_id, nodeId=node_id))
            if canvas and (
                rect.get("x", 0) + rect.get("w", 0) > canvas.get("width", 0) + 0.5
                or rect.get("y", 0) + rect.get("h", 0) > canvas.get("height", 0) + 0.5
            ):
                issues.append(_issue("warning", "LAYOUT_CANVAS", f"{function_id}: node outside canvas", functionId=function_id, nodeId=node_id))
        for index, (a_id, a) in enumerate(rects):
            for b_id, b in rects[index + 1 :]:
                if not (
                    a["x"] + a["w"] <= b["x"] + 0.5
                    or b["x"] + b["w"] <= a["x"] + 0.5
                    or a["y"] + a["h"] <= b["y"] + 0.5
                    or b["y"] + b["h"] <= a["y"] + 0.5
                ):
                    issues.append(_issue("error", "NODE_OVERLAP", f"{function_id}: nodes {a_id} and {b_id} overlap", functionId=function_id, nodeId=a_id))
        for node in nodes.values():
            if node.get("type") == "merge" and node.get("mergeOf") in layout_nodes:
                merge_rect = layout_nodes[node["id"]]
                branch_rect = layout_nodes[node["mergeOf"]]
                if abs(merge_rect["x"] + merge_rect["w"] / 2 - branch_rect["x"] - branch_rect["w"] / 2) > 0.5:
                    issues.append(_issue("error", "MERGE_ALIGN", f"{function_id}: merge not aligned with branch", functionId=function_id, nodeId=node["id"]))
    for edge in edges:
        layout_edge = (layout.get("edges") or {}).get(edge["id"], {})
        d = layout_edge.get("d") or edge.get("d")
        if not d:
            issues.append(_issue("error", "EDGE_PATH", f"{function_id}: edge path missing", functionId=function_id))
            continue
        for message in _check_path(d):
            issues.append(_issue("error", "LAYOUT_PATH", f"{function_id}: {message}", functionId=function_id))
    return issues


def validate_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if bundle.get("kind") != "archmap.bundle":
        issues.append(_issue("error", "BUNDLE_KIND", "top-level kind must be archmap.bundle"))
    if str(bundle.get("schemaVersion")) != "3.0":
        issues.append(_issue("error", "SCHEMA_VERSION", "schemaVersion must be 3.0"))
    project_graph = bundle.get("projectGraph") or {}
    module_graphs = bundle.get("moduleGraphs") or []
    flows = bundle.get("functionFlows") or []
    flow_by_id = {flow.get("id"): flow for flow in flows}
    if len(flow_by_id) != len(flows):
        issues.append(_issue("error", "DUPLICATE_FUNCTION", "duplicate function flow ids"))
    module_ids = {module.get("id") for module in project_graph.get("modules", [])}
    if len(module_ids) != len(project_graph.get("modules", [])):
        issues.append(_issue("error", "DUPLICATE_MODULE", "duplicate module ids"))
    for entry in bundle.get("entrypoints", []):
        if entry.get("functionId") not in flow_by_id:
            issues.append(_issue("error", "ENTRYPOINT_MISSING", f"entrypoint function missing: {entry.get('functionId')}"))
    for module in project_graph.get("modules", []):
        for fn_id in module.get("functions", []):
            if fn_id not in flow_by_id:
                issues.append(_issue("error", "MODULE_FUNCTION_MISSING", f"module {module.get('id')} references missing function {fn_id}"))
    project_node_ids = {node.get("id") for node in project_graph.get("boundaryNodes", [])} | module_ids
    for edge in project_graph.get("edges", []):
        if edge.get("from") not in project_node_ids or edge.get("to") not in project_node_ids:
            issues.append(_issue("error", "PROJECT_EDGE_ENDPOINT", f"project edge endpoint missing: {edge.get('id')}"))
    for graph in module_graphs:
        module_id = graph.get("moduleId")
        node_ids = {node.get("id") for node in graph.get("nodes", [])}
        class_ids = {
            node.get("id") for node in graph.get("nodes", []) if node.get("kind") == "class"
        }
        for node in graph.get("nodes", []):
            if node.get("kind") == "function" and node.get("functionFlowId") not in flow_by_id:
                issues.append(_issue("error", "FLOW_REF_MISSING", f"module {module_id} references missing flow {node.get('functionFlowId')}"))
            if node.get("kind") == "class":
                class_id = node.get("id")
                if not node.get("classKind"):
                    issues.append(_issue("error", "CLASS_KIND_MISSING", f"module {module_id} class {class_id} missing classKind"))
                for method in node.get("methods", []):
                    method_id = method.get("id")
                    if method.get("ownerClassId") != class_id:
                        issues.append(_issue("error", "METHOD_OWNER", f"module {module_id} method {method_id} has wrong ownerClassId"))
                    if method.get("functionFlowId") not in flow_by_id:
                        issues.append(_issue("error", "METHOD_FLOW_MISSING", f"module {module_id} class {class_id} method {method_id} references missing flow"))
                for key in ("publicMethodIds", "entryMethodIds", "exitMethodIds"):
                    for method_id in node.get(key, []):
                        method = flow_by_id.get(method_id)
                        if method is None:
                            issues.append(_issue("error", "CLASS_METHOD_REF", f"module {module_id} class {class_id} references missing method {method_id}"))
                        elif method.get("ownerClassId") != class_id:
                            issues.append(_issue("error", "CLASS_METHOD_OWNER", f"module {module_id} class {class_id} references method {method_id} owned by another class"))
        for edge in graph.get("edges", []):
            if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
                issues.append(_issue("error", "MODULE_EDGE_ENDPOINT", f"module {module_id} edge endpoint missing: {edge.get('id')}"))
        for edge in graph.get("methodEdges", []):
            for endpoint in (edge.get("from"), edge.get("to")):
                if endpoint not in flow_by_id:
                    issues.append(_issue("error", "METHOD_EDGE_ENDPOINT", f"module {module_id} method edge endpoint missing: {endpoint}"))
        for module in project_graph.get("modules", []):
            if module.get("id") != module_id:
                continue
            for class_id in module.get("classes", []):
                if class_id not in class_ids:
                    issues.append(_issue("error", "MODULE_CLASS_MISSING", f"module {module_id} references missing class {class_id}"))
    for flow in flows:
        issues.extend(_validate_function(flow))
    for issue in issues:
        if "imports" in issue.get("message", "") or "calls\"" in issue.get("message", ""):
            issue["code"] = "LEGACY_EDGE"
    return issues
