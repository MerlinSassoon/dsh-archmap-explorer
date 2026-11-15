from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .analysis import AnalysisResult, FunctionInfo
from .config import ModuleConfig, ProjectConfig


MODULE_W = 270
MODULE_H = 140
MODULE_EXPANDED_W = 560
MODULE_EXPANDED_H = 360
FUNCTION_W = 210
FUNCTION_H = 98
BOUNDARY_W = 190
BOUNDARY_H = 96
MACRO_X_GAP = 360
MACRO_Y_GAP = 180
MACRO_PAD = 70


PALETTE = ["#f59e0b", "#60a5fa", "#8bdc64", "#a78bfa", "#f472b6", "#22d3ee", "#fb7185"]


@dataclass
class CallRecord:
    from_function: str
    to_function: str
    from_module: str
    to_module: str
    file: str
    line: int
    has_data: bool
    external: bool = False


def _json_hash(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def _edge_id(prefix: str, index: int) -> str:
    return f"e:{prefix}:{index}"


def _boundary_id(scope: str, kind: str, index: int) -> str:
    return f"{scope}:{kind}:{index}"


def _function_lookup(analysis: AnalysisResult) -> dict[str, FunctionInfo]:
    return {fn.id: fn for fn in analysis.functions}


def find_entrypoints(analysis: AnalysisResult, flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    functions = _function_lookup(analysis)
    module_by_name = {module.name: module for module in analysis.modules}
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(fn_id: str, reason: str) -> None:
        if fn_id in functions and fn_id not in seen:
            seen.add(fn_id)
            found.append({"functionId": fn_id, "reason": reason})

    for spec in analysis.config.entrypoints:
        spec = spec.strip()
        if not spec:
            continue
        if ":" in spec:
            left, right = spec.rsplit(":", 1)
            module_name = left.removesuffix(".py").split("/")[-1]
            module = module_by_name.get(module_name) or next(
                (item for item in analysis.modules if item.name.split(".")[-1] == module_name),
                None,
            )
            if module:
                fn = module.functions.get(right)
                if fn:
                    add(fn.id, "configured")
                    continue
                matches = [item for item in module.functions.values() if item.name == right]
                if matches:
                    add(sorted(matches, key=lambda item: item.id)[0].id, "configured")
                    continue
        # Bare module name, bare function name, or module.py path.
        module_name = spec.removesuffix(".py").split("/")[-1]
        module = module_by_name.get(module_name) or next(
            (item for item in analysis.modules if item.name.split(".")[-1] == module_name),
            None,
        )
        if module:
            main_fn = module.functions.get("__main__") or module.functions.get("main")
            if main_fn:
                add(main_fn.id, "configured")
                continue
        matches = [fn for fn in analysis.functions if fn.name == spec or fn.qualname == spec]
        for fn in sorted(matches, key=lambda item: item.id):
            add(fn.id, "configured")

    if analysis.config.entrypoints and found:
        return found

    # Prefer synthetic script entry functions.
    for fn in sorted(analysis.functions, key=lambda item: item.id):
        if fn.synthetic:
            add(fn.id, "main")
    # Conventional names.
    for name in ("main", "cli", "run"):
        for fn in sorted(analysis.functions, key=lambda item: item.id):
            if fn.name == name and not fn.class_name:
                add(fn.id, "heuristic")
    # Graph heuristic: exported functions with no project-internal incoming calls.
    incoming: set[str] = set()
    for flow in flows:
        for node in flow["nodes"]:
            call = node.get("call") or {}
            target = call.get("targetFunctionId")
            if target:
                incoming.add(target)
    for fn in sorted(analysis.functions, key=lambda item: item.id):
        if fn.class_name or fn.name.startswith("_"):
            continue
        if fn.id not in incoming:
            add(fn.id, "heuristic")
    return found


def collect_calls(analysis: AnalysisResult, flows: Iterable[dict[str, Any]]) -> list[CallRecord]:
    fn_by_id = _function_lookup(analysis)
    records: list[CallRecord] = []
    for flow in flows:
        for node in flow["nodes"]:
            call = node.get("call")
            if not call or not call.get("resolved"):
                continue
            target_id = call.get("targetFunctionId")
            if not target_id or target_id not in fn_by_id:
                continue
            target = fn_by_id[target_id]
            source = fn_by_id[flow["id"]]
            data = node.get("data") or {}
            records.append(
                CallRecord(
                    from_function=source.id,
                    to_function=target.id,
                    from_module=source.module_id,
                    to_module=target.module_id,
                    file=node.get("file", source.file),
                    line=int(node.get("line", source.line)),
                    has_data=bool(data.get("defs") or data.get("uses")),
                )
            )
    return records


def _aggregate_relations(records: list[CallRecord]) -> dict[str, str]:
    relations = {"call"}
    if any(record.has_data for record in records):
        relations.add("data")
    primary = "call" if "call" in relations else "data"
    return {"primaryType": primary, "relations": sorted(relations)}


def _macro_edge(
    edge_id: str,
    from_id: str,
    to_id: str,
    *,
    primary_type: str,
    relations: list[str],
    role: str,
    evidence: list[dict[str, Any]] | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "from": from_id,
        "to": to_id,
        "primaryType": primary_type,
        "relations": sorted(set(relations)),
        "role": role,
        "confidence": confidence,
        "evidence": evidence or [],
    }


def _module_input_labels(module: ModuleConfig) -> list[str]:
    return module.inputs or ["模块输入"]


def _module_output_labels(module: ModuleConfig) -> list[str]:
    return module.outputs or ["模块输出"]


def _curve_d(src: dict[str, Any], dst: dict[str, Any]) -> str:
    sx = src["x"] + src["w"] if dst["x"] >= src["x"] else src["x"]
    sy = src["y"] + src["h"] / 2
    tx = dst["x"] if dst["x"] >= src["x"] else dst["x"] + dst["w"]
    ty = dst["y"] + dst["h"] / 2
    dx = max(70.0, min(220.0, abs(tx - sx) * 0.48))
    sign = 1 if tx >= sx else -1
    c1x = sx + sign * dx
    c2x = tx - sign * dx
    return (
        f"M {round(sx, 2)} {round(sy, 2)} "
        f"C {round(c1x, 2)} {round(sy, 2)} {round(c2x, 2)} {round(ty, 2)} "
        f"{round(tx, 2)} {round(ty, 2)}"
    )


def _scc_order(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[dict[str, int], list[list[str]]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        adjacency[src].append(dst)

    index = 0
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in sorted(set(adjacency.get(node, []))):
            if nxt not in indices:
                strongconnect(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], indices[nxt])
        if low[node] == indices[node]:
            comp: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                comp.append(item)
                if item == node:
                    break
            components.append(sorted(comp))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)
    component_of: dict[str, int] = {}
    for idx, comp in enumerate(components):
        for node in comp:
            component_of[node] = idx
    comp_edges: set[tuple[int, int]] = set()
    for src, dst in edges:
        if component_of[src] != component_of[dst]:
            comp_edges.add((component_of[src], component_of[dst]))
    indegree = {idx: 0 for idx in range(len(components))}
    cadj: dict[int, list[int]] = defaultdict(list)
    for src, dst in comp_edges:
        cadj[src].append(dst)
        indegree[dst] += 1
    queue = deque(sorted(idx for idx, value in indegree.items() if value == 0))
    rank: dict[int, int] = {idx: 0 for idx in queue}
    while queue:
        current = queue.popleft()
        for nxt in sorted(set(cadj[current])):
            rank[nxt] = max(rank.get(nxt, 0), rank[current] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return {node: rank.get(component_of[node], 0) for node in nodes}, components


def _layout_macro(
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    boundary_ids: set[str],
    scope: str,
) -> dict[str, Any]:
    node_ids = sorted(nodes)
    graph_edges = [
        (edge["from"], edge["to"])
        for edge in edges
        if edge["from"] in nodes and edge["to"] in nodes and edge["from"] != edge["to"]
    ]
    ranks, _ = _scc_order(node_ids, graph_edges)
    rank_groups: dict[int, list[str]] = defaultdict(list)
    for node_id in node_ids:
        rank_groups[ranks[node_id]].append(node_id)

    positions: dict[str, dict[str, Any]] = {}
    for rank in sorted(rank_groups):
        group = rank_groups[rank]
        group.sort(key=lambda item: (0 if item in boundary_ids else 1, item))
        total_height = (len(group) - 1) * MACRO_Y_GAP
        start_y = 160 - total_height / 2
        for index, node_id in enumerate(group):
            node = nodes[node_id]
            x = MACRO_PAD + 220 + rank * MACRO_X_GAP
            y = start_y + index * MACRO_Y_GAP
            positions[node_id] = {
                "x": round(x, 2),
                "y": round(y, 2),
                "w": node.get("w", MODULE_W),
                "h": node.get("h", MODULE_H),
            }

    # Keep boundary nodes visually outside the module flow.
    for node_id in boundary_ids:
        node = nodes.get(node_id)
        if not node:
            continue
        if node.get("kind") == "input":
            positions[node_id]["x"] = MACRO_PAD
        elif node.get("kind") == "output":
            max_x = max((pos["x"] + pos["w"] for pos in positions.values()), default=300)
            positions[node_id]["x"] = round(max_x + MACRO_X_GAP / 2, 2)

    min_x = min((pos["x"] for pos in positions.values()), default=0)
    min_y = min((pos["y"] for pos in positions.values()), default=0)
    max_x = max((pos["x"] + pos["w"] for pos in positions.values()), default=400)
    max_y = max((pos["y"] + pos["h"] for pos in positions.values()), default=300)
    dx = MACRO_PAD - min_x
    dy = MACRO_PAD - min_y
    for pos in positions.values():
        pos["x"] = round(pos["x"] + dx, 2)
        pos["y"] = round(pos["y"] + dy, 2)
    canvas = {
        "width": round(max_x + dx + MACRO_PAD, 2),
        "height": round(max_y + dy + MACRO_PAD, 2),
        "padding": MACRO_PAD,
    }
    layout_edges: dict[str, Any] = {}
    for edge in edges:
        src = positions.get(edge["from"])
        dst = positions.get(edge["to"])
        if not src or not dst:
            continue
        layout_edges[edge["id"]] = {"d": _curve_d(src, dst)}
    return {"canvas": canvas, "nodes": positions, "edges": layout_edges}


def _module_color(index: int, module: ModuleConfig | None) -> str:
    if module and module.color:
        return module.color
    return PALETTE[index % len(PALETTE)]


def build_bundle(analysis: AnalysisResult, flows: list[dict[str, Any]]) -> dict[str, Any]:
    config = analysis.config
    fn_by_id = _function_lookup(analysis)
    module_configs = {module.id: module for module in config.modules}
    entrypoints = find_entrypoints(analysis, flows)
    entry_ids = [item["functionId"] for item in entrypoints]
    calls = collect_calls(analysis, flows)

    module_function_ids: dict[str, list[str]] = defaultdict(list)
    for fn in analysis.functions:
        module_function_ids[fn.module_id].append(fn.id)
    for module_id in module_function_ids:
        module_function_ids[module_id].sort()

    ordered_module_ids = [module.id for module in config.modules]
    for module_id in sorted(module_function_ids):
        if module_id not in ordered_module_ids:
            ordered_module_ids.append(module_id)
    if not ordered_module_ids:
        ordered_module_ids = ["main"]

    project_nodes: dict[str, dict[str, Any]] = {}
    project_module_nodes: list[dict[str, Any]] = []
    project_inputs: list[dict[str, Any]] = []
    project_outputs: list[dict[str, Any]] = []

    for index, label in enumerate(config.inputs or ["用户输入"]):
        node_id = _boundary_id("project", "input", index)
        project_nodes[node_id] = {
            "id": node_id,
            "kind": "input",
            "label": label,
            "note": "项目外部输入",
            "w": BOUNDARY_W,
            "h": BOUNDARY_H,
        }
        project_inputs.append({"id": node_id, "label": label})
    for index, label in enumerate(config.outputs or ["用户输出"]):
        node_id = _boundary_id("project", "output", index)
        project_nodes[node_id] = {
            "id": node_id,
            "kind": "output",
            "label": label,
            "note": "项目外部输出",
            "w": BOUNDARY_W,
            "h": BOUNDARY_H,
        }
        project_outputs.append({"id": node_id, "label": label})

    module_graphs: list[dict[str, Any]] = []
    for index, module_id in enumerate(ordered_module_ids):
        configured = module_configs.get(module_id)
        function_ids = module_function_ids.get(module_id, [])
        module_name = configured.name if configured else module_id
        module_note = configured.note if configured else ""
        input_labels = _module_input_labels(configured) if configured else ["模块输入"]
        output_labels = _module_output_labels(configured) if configured else ["模块输出"]
        color = _module_color(index, configured)
        module_node = {
            "id": module_id,
            "kind": "module",
            "name": module_name,
            "note": module_note,
            "color": color,
            "functions": function_ids,
            "inputs": [{"id": _boundary_id(f"module:{module_id}", "input", i), "label": label} for i, label in enumerate(input_labels)],
            "outputs": [{"id": _boundary_id(f"module:{module_id}", "output", i), "label": label} for i, label in enumerate(output_labels)],
            "sourceFiles": sorted({fn_by_id[fn_id].file for fn_id in function_ids if fn_id in fn_by_id}),
            "w": MODULE_W,
            "h": MODULE_H,
            "expandedW": MODULE_EXPANDED_W,
            "expandedH": MODULE_EXPANDED_H,
        }
        project_nodes[module_id] = module_node
        project_module_nodes.append(module_node)

        # Module-level graph.
        module_nodes: dict[str, dict[str, Any]] = {}
        boundaries: set[str] = set()
        for port in module_node["inputs"]:
            node_id = port["id"]
            boundaries.add(node_id)
            module_nodes[node_id] = {
                "id": node_id,
                "kind": "input",
                "label": port["label"],
                "note": f"{module_name} 的输入",
                "w": BOUNDARY_W,
                "h": BOUNDARY_H,
            }
        for port in module_node["outputs"]:
            node_id = port["id"]
            boundaries.add(node_id)
            module_nodes[node_id] = {
                "id": node_id,
                "kind": "output",
                "label": port["label"],
                "note": f"{module_name} 的输出",
                "w": BOUNDARY_W,
                "h": BOUNDARY_H,
            }
        for fn_id in function_ids:
            fn = fn_by_id[fn_id]
            module_nodes[fn_id] = {
                "id": fn_id,
                "kind": "function",
                "uid": fn_id,
                "name": fn.name,
                "qualifiedName": f"{fn.module_name}.{fn.qualname}",
                "note": fn.note,
                "file": fn.file,
                "line": fn.line,
                "functionFlowId": fn_id,
                "w": FUNCTION_W,
                "h": FUNCTION_H,
            }

        internal_records = [
            record
            for record in calls
            if record.from_module == module_id and record.to_module == module_id
        ]
        aggregate: dict[tuple[str, str], list[CallRecord]] = defaultdict(list)
        for record in internal_records:
            aggregate[(record.from_function, record.to_function)].append(record)
        module_edges: list[dict[str, Any]] = []
        for edge_index, ((from_id, to_id), records) in enumerate(sorted(aggregate.items()), start=1):
            semantics = _aggregate_relations(records)
            evidence = [
                {
                    "fromFunctionId": record.from_function,
                    "toFunctionId": record.to_function,
                    "file": record.file,
                    "line": record.line,
                }
                for record in records
            ]
            module_edges.append(
                _macro_edge(
                    _edge_id(f"module:{module_id}", edge_index),
                    from_id,
                    to_id,
                    primary_type=semantics["primaryType"],
                    relations=semantics["relations"],
                    role="internal",
                    evidence=evidence,
                    confidence="high" if len(records) == 1 else "medium",
                )
            )

        internal_incoming = {edge["to"] for edge in module_edges}
        internal_outgoing = {edge["from"] for edge in module_edges}
        input_boundary = module_node["inputs"][0]["id"]
        output_boundary = module_node["outputs"][0]["id"]
        boundary_seed = [
            fn_id
            for fn_id in function_ids
            if fn_id in entry_ids or fn_id not in internal_incoming
        ]
        if not boundary_seed and function_ids:
            boundary_seed = [function_ids[0]]
        for fn_id in boundary_seed:
            idx = len(module_edges) + 1
            module_edges.append(
                _macro_edge(
                    _edge_id(f"module:{module_id}", idx),
                    input_boundary,
                    fn_id,
                    primary_type="control",
                    relations=["control"],
                    role="module_input",
                    evidence=[],
                    confidence="low",
                )
            )
        terminal = [fn_id for fn_id in function_ids if fn_id not in internal_outgoing]
        if not terminal and function_ids:
            terminal = [function_ids[-1]]
        for fn_id in terminal:
            idx = len(module_edges) + 1
            module_edges.append(
                _macro_edge(
                    _edge_id(f"module:{module_id}", idx),
                    fn_id,
                    output_boundary,
                    primary_type="control",
                    relations=["control"],
                    role="module_output",
                    evidence=[],
                    confidence="low",
                )
            )
        module_layout = _layout_macro(module_nodes, module_edges, boundary_ids=boundaries, scope=f"module:{module_id}")
        module_graphs.append(
            {
                "kind": "archmap.module-graph",
                "moduleId": module_id,
                "name": module_name,
                "note": module_note,
                "color": color,
                "inputs": module_node["inputs"],
                "outputs": module_node["outputs"],
                "nodes": [module_nodes[node_id] for node_id in sorted(module_nodes)],
                "edges": module_edges,
                "layout": module_layout,
            }
        )

    # Project-level aggregated cross-module calls.
    project_edges: list[dict[str, Any]] = []
    cross_by_pair: dict[tuple[str, str], list[CallRecord]] = defaultdict(list)
    for record in calls:
        if record.from_module != record.to_module:
            cross_by_pair[(record.from_module, record.to_module)].append(record)
    for edge_index, ((from_id, to_id), records) in enumerate(sorted(cross_by_pair.items()), start=1):
        semantics = _aggregate_relations(records)
        evidence = [
            {
                "fromFunctionId": record.from_function,
                "toFunctionId": record.to_function,
                "file": record.file,
                "line": record.line,
            }
            for record in records
        ]
        project_edges.append(
            _macro_edge(
                _edge_id("project", edge_index),
                from_id,
                to_id,
                primary_type=semantics["primaryType"],
                relations=semantics["relations"],
                role="internal",
                evidence=evidence,
                confidence="high" if len(records) == 1 else "medium",
            )
        )

    project_edges.sort(key=lambda edge: (edge["from"], edge["to"], edge["id"]))
    entry_modules = {fn_by_id[fn_id].module_id for fn_id in entry_ids if fn_id in fn_by_id}
    modules_with_incoming = {edge["to"] for edge in project_edges}
    modules_with_outgoing = {edge["from"] for edge in project_edges}
    input_seed = sorted(module_id for module_id in ordered_module_ids if module_id in entry_modules)
    if not input_seed:
        input_seed = sorted(module_id for module_id in ordered_module_ids if module_id not in modules_with_incoming)
    if not input_seed and ordered_module_ids:
        input_seed = [ordered_module_ids[0]]
    if project_inputs:
        input_id = project_inputs[0]["id"]
        for module_id in input_seed:
            project_edges.append(
                _macro_edge(
                    _edge_id("project", len(project_edges) + 1),
                    input_id,
                    module_id,
                    primary_type="control",
                    relations=["control"],
                    role="project_input",
                    confidence="low",
                )
            )
    output_seed = sorted(module_id for module_id in ordered_module_ids if module_id not in modules_with_outgoing)
    if not output_seed and ordered_module_ids:
        output_seed = [ordered_module_ids[-1]]
    if project_outputs:
        output_id = project_outputs[0]["id"]
        for module_id in output_seed:
            project_edges.append(
                _macro_edge(
                    _edge_id("project", len(project_edges) + 1),
                    module_id,
                    output_id,
                    primary_type="control",
                    relations=["control"],
                    role="project_output",
                    confidence="low",
                )
            )

    boundary_ids = set(project_inputs and [item["id"] for item in project_inputs] or [])
    boundary_ids.update(item["id"] for item in project_outputs)
    project_layout = _layout_macro(project_nodes, project_edges, boundary_ids=boundary_ids, scope="project")
    project_graph = {
        "kind": "archmap.project-graph",
        "project": {
            "name": config.name,
            "language": config.language,
            "inputs": [item["label"] for item in project_inputs],
            "outputs": [item["label"] for item in project_outputs],
        },
        "boundaryNodes": [project_nodes[item["id"]] for item in project_inputs + project_outputs],
        "modules": project_module_nodes,
        "edges": project_edges,
        "layout": project_layout,
    }

    # Per-function source hashes for LLM annotations.
    for flow in flows:
        semantic = {
            "id": flow["id"],
            "file": flow["file"],
            "line": flow["line"],
            "endLine": flow["endLine"],
            "signature": flow["signature"],
            "nodes": [
                {
                    "id": node["id"],
                    "type": node["type"],
                    "stepType": node.get("stepType"),
                    "code": node.get("code"),
                    "line": node.get("line"),
                    "call": (node.get("call") or {}).get("targetFunctionId"),
                }
                for node in flow["nodes"]
                if not node.get("synthetic")
            ],
        }
        flow["sourceHash"] = _json_hash(semantic)

    diagnostics = list(analysis.diagnostics)
    for flow in flows:
        diagnostics.extend(flow.pop("diagnostics", []))
    max_rank = max(
        (
            item["rank"]
            for flow in flows
            for item in flow.get("layout", {}).get("nodes", {}).values()
        ),
        default=0,
    )
    stats = {
        "modules": len(project_module_nodes),
        "functions": len(flows),
        "nodes": sum(len(flow["nodes"]) for flow in flows),
        "edges": sum(len(flow["edges"]) for flow in flows),
        "macroEdges": len(project_edges) + sum(len(graph["edges"]) for graph in module_graphs),
        "maxRank": max_rank,
        "diagnostics": {
            level: sum(1 for item in diagnostics if item.get("severity") == level)
            for level in ("error", "warning", "info")
        },
    }
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if os.environ.get("SOURCE_DATE_EPOCH"):
        try:
            generated_at = datetime.fromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    bundle = {
        "schemaVersion": "3.0",
        "kind": "archmap.bundle",
        "project": {
            "name": config.name,
            "root": ".",
            "language": config.language,
            "generatedAt": generated_at,
            "fingerprint": "sha256:" + "0" * 64,
        },
        "entrypoints": entrypoints,
        "projectGraph": project_graph,
        "moduleGraphs": module_graphs,
        "functionFlows": sorted(flows, key=lambda item: item["id"]),
        "diagnostics": diagnostics,
        "stats": stats,
    }
    bundle["project"]["fingerprint"] = semantic_fingerprint(bundle)
    return bundle


def semantic_fingerprint(bundle: dict[str, Any]) -> str:
    semantic = {
        "schemaVersion": bundle["schemaVersion"],
        "project": {
            "name": bundle["project"]["name"],
            "language": bundle["project"]["language"],
        },
        "entrypoints": sorted(bundle["entrypoints"], key=lambda item: item["functionId"]),
        "projectGraph": {
            "modules": [
                {
                    "id": module["id"],
                    "name": module["name"],
                    "note": module["note"],
                    "functions": sorted(module["functions"]),
                    "inputs": module["inputs"],
                    "outputs": module["outputs"],
                }
                for module in sorted(bundle["projectGraph"]["modules"], key=lambda item: item["id"])
            ],
            "edges": sorted(
                [
                    {
                        "from": edge["from"],
                        "to": edge["to"],
                        "primaryType": edge["primaryType"],
                        "relations": edge["relations"],
                        "role": edge["role"],
                        "evidence": edge.get("evidence", []),
                    }
                    for edge in bundle["projectGraph"]["edges"]
                ],
                key=lambda item: (item["from"], item["to"], item["primaryType"], item["role"]),
            ),
        },
        "moduleGraphs": sorted(
            [
                {
                    "moduleId": graph["moduleId"],
                    "note": graph["note"],
                    "edges": sorted(
                        [
                            {
                                "from": edge["from"],
                                "to": edge["to"],
                                "primaryType": edge["primaryType"],
                                "relations": edge["relations"],
                                "role": edge["role"],
                                "evidence": edge.get("evidence", []),
                            }
                            for edge in graph["edges"]
                        ],
                        key=lambda item: (item["from"], item["to"], item["primaryType"], item["role"]),
                    ),
                }
                for graph in bundle["moduleGraphs"]
            ],
            key=lambda item: item["moduleId"],
        ),
        "functionFlows": sorted(
            [
                {
                    "id": flow["id"],
                    "note": flow["note"],
                    "qualifiedName": flow["qualifiedName"],
                    "signature": flow["signature"],
                    "sourceHash": flow["sourceHash"],
                    "nodes": [
                        {
                            "id": node["id"],
                            "type": node["type"],
                            "stepType": node.get("stepType"),
                            "code": node.get("code"),
                            "line": node.get("line"),
                            "endLine": node.get("endLine"),
                            "order": node.get("order"),
                            "callTarget": (node.get("call") or {}).get("targetFunctionId"),
                        }
                        for node in sorted(flow["nodes"], key=lambda item: item["id"])
                    ],
                    "edges": sorted(
                        [
                            {
                                "from": edge["from"],
                                "to": edge["to"],
                                "type": edge["type"],
                                "flow": edge.get("flow"),
                                "variable": edge.get("variable"),
                                "resolution": edge.get("resolution"),
                            }
                            for edge in flow["edges"]
                        ],
                        key=lambda item: (item["from"], item["to"], item["type"], item.get("flow") or ""),
                    ),
                }
                for flow in bundle["functionFlows"]
            ],
            key=lambda item: item["id"],
        ),
    }
    return _json_hash(semantic)
