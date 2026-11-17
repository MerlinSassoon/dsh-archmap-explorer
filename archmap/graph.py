from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .analysis import AnalysisResult, ClassInfo, ENTRY_METHOD_NAMES, FunctionInfo
from .callsites import CallSite
from .config import MODULE_ROLES, ModuleConfig, ProjectConfig


MODULE_W = 320
MODULE_H = 200
MODULE_MAIN_W = 360
MODULE_MAIN_H = 230
MODULE_EXPANDED_W = 620
MODULE_EXPANDED_H = 430
MODULE_MAIN_EXPANDED_W = 660
MODULE_MAIN_EXPANDED_H = 470
MODULE_CARD_COLUMNS = 3
MODULE_CARD_GAP_X = 80
MODULE_CARD_GAP_Y = 70
FUNCTION_W = 210
FUNCTION_H = 98
CLASS_W = 280
CLASS_H = 150
BOUNDARY_W = 170
BOUNDARY_H = 78
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


def _class_id(cls: ClassInfo) -> str:
    return f"cls:{cls.module_name}.{cls.qualname}"


def _method_component_id(fn: FunctionInfo) -> str:
    if fn.class_name:
        return f"cls:{fn.module_name}.{fn.class_name}"
    return fn.id


def _method_summary(fn: FunctionInfo, owner_class_id: str) -> dict[str, Any]:
    return {
        "id": fn.id,
        "kind": "method",
        "name": fn.name,
        "qualifiedName": f"{fn.module_name}.{fn.qualname}",
        "ownerClassId": owner_class_id,
        "methodKind": fn.method_kind,
        "visibility": fn.visibility,
        "isAbstract": fn.is_abstract,
        "signature": fn.signature,
        "note": fn.note,
        "file": fn.file,
        "line": fn.line,
        "endLine": fn.end_line,
        "functionDetailId": fn.id,
    }


def _class_entry_methods(
    methods: list[FunctionInfo], configured_entry_ids: set[str] | None = None
) -> list[FunctionInfo]:
    public = [
        method
        for method in methods
        if method.visibility in {"public", "lifecycle"}
        and not method.is_abstract
        and method.method_kind not in {"constructor", "internal", "dunder"}
    ]
    if configured_entry_ids:
        configured = [method for method in public if method.id in configured_entry_ids]
        if configured:
            return configured
    named = [
        method
        for method in public
        if method.name in ENTRY_METHOD_NAMES | {"__call__", "__enter__"}
    ]
    return named or public


def _module_role(module: ModuleConfig | None, module_id: str, entry_module_ids: set[str]) -> str:
    """Resolve an explicit module role, falling back to a light heuristic.

    The role is presentation metadata, not a structural fact.  Explicit config
    always wins; otherwise the module that owns a configured/derived entrypoint
    is treated as the main module.  Everything else is a service module.
    """
    if module is not None and module.role:
        role = module.role.strip().lower()
        if role in MODULE_ROLES:
            return role
    if module_id in entry_module_ids:
        return "main"
    return "service"


def _provided_api_entry(
    fn: FunctionInfo,
    *,
    module_id: str,
    module_name: str,
    owner_id: str,
    owner_name: str,
    owner_kind: str,
    owner_class_kind: str,
    entry_id_set: set[str],
) -> dict[str, Any]:
    is_abstract = bool(fn.is_abstract)
    kind = "function"
    if owner_kind == "class":
        kind = "abstract_method" if is_abstract else "method"
    return {
        "id": f"api:{fn.id}",
        "kind": kind,
        "name": fn.name,
        "qualifiedName": f"{fn.module_name}.{fn.qualname}",
        "ownerId": owner_id,
        "ownerName": owner_name,
        "ownerKind": owner_kind,
        "ownerClassKind": owner_class_kind,
        "moduleId": module_id,
        "moduleName": module_name,
        "functionId": fn.id,
        "functionDetailId": fn.id,
        "signature": fn.signature,
        "note": fn.note,
        "methodKind": fn.method_kind,
        "visibility": fn.visibility,
        "isAbstract": is_abstract,
        "isEntry": fn.id in entry_id_set,
        "file": fn.file,
        "line": fn.line,
        "endLine": fn.end_line,
    }


def _module_provided_apis(
    module_id: str,
    module_name: str,
    module_classes: list[ClassInfo],
    class_method_meta: dict[str, list[FunctionInfo]],
    free_function_ids: list[str],
    fn_by_id: dict[str, FunctionInfo],
    entry_id_set: set[str],
) -> list[dict[str, Any]]:
    """Derive the module's externally callable surface from existing facts.

    ``providedApis`` is a projection, not a second source of truth.  It is
    built from public class methods (including abstract contract methods) and
    public module-level free functions.  Constructors, dunder methods and
    underscore-prefixed internals stay out of the capability card.
    """
    entries: list[dict[str, Any]] = []
    for cls in module_classes:
        cls_id = _class_id(cls)
        methods = class_method_meta.get(cls_id, [])
        for method in methods:
            if method.method_kind in {"constructor", "dunder", "internal"}:
                continue
            if method.visibility in {"constructor", "dunder", "internal"}:
                continue
            entries.append(
                _provided_api_entry(
                    method,
                    module_id=module_id,
                    module_name=module_name,
                    owner_id=cls_id,
                    owner_name=cls.name,
                    owner_kind="class",
                    owner_class_kind=cls.class_kind,
                    entry_id_set=entry_id_set,
                )
            )
    for fn_id in free_function_ids:
        fn = fn_by_id.get(fn_id)
        if fn is None:
            continue
        if fn.visibility != "public":
            continue
        if fn.name.startswith("_") and not fn.synthetic:
            continue
        entries.append(
            _provided_api_entry(
                fn,
                module_id=module_id,
                module_name=module_name,
                owner_id=module_id,
                owner_name=module_name,
                owner_kind="module",
                owner_class_kind="",
                entry_id_set=entry_id_set,
            )
        )
    entries.sort(
        key=lambda item: (
            0 if item["isEntry"] else 1,
            0 if item["ownerKind"] == "class" else 1,
            item["ownerName"],
            item["line"],
            item["id"],
        )
    )
    return entries


def find_entrypoints(analysis: AnalysisResult, call_sites: Iterable[CallSite]) -> list[dict[str, Any]]:
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
    incoming: set[str] = {
        site.to_function_id
        for site in call_sites
        if site.resolved and site.to_function_id
    }
    for fn in sorted(analysis.functions, key=lambda item: item.id):
        if fn.class_name or fn.name.startswith("_"):
            continue
        if fn.id not in incoming:
            add(fn.id, "heuristic")
    return found


def collect_calls(analysis: AnalysisResult, call_sites: Iterable[CallSite]) -> list[CallRecord]:
    fn_by_id = _function_lookup(analysis)
    records: list[CallRecord] = []
    for site in call_sites:
        if not site.resolved or not site.to_function_id:
            continue
        target = fn_by_id.get(site.to_function_id)
        source = fn_by_id.get(site.from_function_id)
        if target is None or source is None:
            continue
        records.append(
            CallRecord(
                from_function=source.id,
                to_function=target.id,
                from_module=source.module_id,
                to_module=target.module_id,
                file=site.file,
                line=site.line,
                has_data=site.argument_count > 0,
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


def _layout_module_cards(modules: list[dict[str, Any]]) -> dict[str, Any]:
    """Lay out project-page capability cards without implying dependency flow.

    The main module occupies a dedicated left column; service/adapter/test
    modules flow through a deterministic grid to its right.  This replaces the
    old macro rank layout for the project page, where hiding dependency lines
    would otherwise leave a meaningless single column.
    """
    main_modules = [module for module in modules if module.get("role") == "main"]
    other_modules = [module for module in modules if module.get("role") != "main"]
    positions: dict[str, dict[str, Any]] = {}

    main_column_w = 0
    y = MACRO_PAD
    for module in main_modules:
        w = int(module.get("w", MODULE_MAIN_W))
        h = int(module.get("h", MODULE_MAIN_H))
        positions[module["id"]] = {"x": round(float(MACRO_PAD), 2), "y": round(float(y), 2), "w": w, "h": h}
        main_column_w = max(main_column_w, w)
        y += h + MODULE_CARD_GAP_Y

    grid_x = MACRO_PAD + (main_column_w + MODULE_CARD_GAP_X if main_modules else 0)
    # Keep small capability boards readable in a typical viewport.  Two
    # service columns scale better than one long row; larger boards use three.
    columns = 2 if len(other_modules) <= 4 else MODULE_CARD_COLUMNS
    for index, module in enumerate(other_modules):
        col = index % columns
        row = index // columns
        w = int(module.get("w", MODULE_W))
        h = int(module.get("h", MODULE_H))
        x = grid_x + col * (MODULE_W + MODULE_CARD_GAP_X)
        y = MACRO_PAD + row * (MODULE_H + MODULE_CARD_GAP_Y)
        positions[module["id"]] = {"x": round(float(x), 2), "y": round(float(y), 2), "w": w, "h": h}

    max_x = max((pos["x"] + pos["w"] for pos in positions.values()), default=400)
    max_y = max((pos["y"] + pos["h"] for pos in positions.values()), default=300)
    return {
        "mode": "module-cards",
        "canvas": {
            "width": round(max_x + MACRO_PAD, 2),
            "height": round(max_y + MACRO_PAD, 2),
            "padding": MACRO_PAD,
        },
        "nodes": positions,
        "edges": {},
    }


def _module_color(index: int, module: ModuleConfig | None) -> str:
    if module and module.color:
        return module.color
    return PALETTE[index % len(PALETTE)]


def build_bundle(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    function_details: list[dict[str, Any]],
) -> dict[str, Any]:
    config = analysis.config
    fn_by_id = _function_lookup(analysis)
    call_site_list = list(call_sites)
    module_configs = {module.id: module for module in config.modules}
    entrypoints = find_entrypoints(analysis, call_site_list)
    entry_ids = [item["functionId"] for item in entrypoints]
    entry_id_set = set(entry_ids)
    entry_reasons = {item["functionId"]: item["reason"] for item in entrypoints}
    entry_module_ids = {
        fn_by_id[item["functionId"]].module_id
        for item in entrypoints
        if item["functionId"] in fn_by_id
    }
    calls = collect_calls(analysis, call_site_list)

    module_function_ids: dict[str, list[str]] = defaultdict(list)
    for fn in analysis.functions:
        module_function_ids[fn.module_id].append(fn.id)
    for module_id in module_function_ids:
        module_function_ids[module_id].sort()

    # Classes are projected into their owning logical module.  A class may
    # exist without a method being represented in module_function_ids if the
    # source contains only class-level declarations; keep such modules visible.
    classes_by_module: dict[str, list[ClassInfo]] = defaultdict(list)
    for cls in analysis.classes:
        classes_by_module[cls.module_id].append(cls)

    ordered_module_ids = [module.id for module in config.modules]
    for module_id in sorted(set(module_function_ids) | set(classes_by_module)):
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
        module_classes = sorted(classes_by_module.get(module_id, []), key=lambda item: item.qualname)
        class_ids = [_class_id(cls) for cls in module_classes]
        free_function_ids = [
            fn_id for fn_id in function_ids
            if fn_id in fn_by_id and fn_by_id[fn_id].class_name is None
        ]
        method_function_ids = [
            fn_id for fn_id in function_ids
            if fn_id in fn_by_id and fn_by_id[fn_id].class_name is not None
        ]
        module_name = configured.name if configured else module_id
        module_note = configured.note if configured else ""
        input_labels = _module_input_labels(configured) if configured else ["模块输入"]
        output_labels = _module_output_labels(configured) if configured else ["模块输出"]
        color = _module_color(index, configured)
        role = _module_role(configured, module_id, entry_module_ids)
        is_main = role == "main"
        module_node = {
            "id": module_id,
            "kind": "module",
            "name": module_name,
            "note": module_note,
            "color": color,
            "role": role,
            "functions": function_ids,
            "freeFunctions": free_function_ids,
            "classes": class_ids,
            "methods": method_function_ids,
            "inputs": [{"id": _boundary_id(f"module:{module_id}", "input", i), "label": label} for i, label in enumerate(input_labels)],
            "outputs": [{"id": _boundary_id(f"module:{module_id}", "output", i), "label": label} for i, label in enumerate(output_labels)],
            "sourceFiles": sorted({
                *(fn_by_id[fn_id].file for fn_id in function_ids if fn_id in fn_by_id),
                *(cls.file for cls in module_classes if cls.file),
            }),
            "w": MODULE_MAIN_W if is_main else MODULE_W,
            "h": MODULE_MAIN_H if is_main else MODULE_H,
            "expandedW": MODULE_MAIN_EXPANDED_W if is_main else MODULE_EXPANDED_W,
            "expandedH": MODULE_MAIN_EXPANDED_H if is_main else MODULE_EXPANDED_H,
        }
        project_nodes[module_id] = module_node
        project_module_nodes.append(module_node)

        # Module-level graph.  Classes and free functions are the visible
        # component nodes; methods remain owned by the class node and are
        # projected into the method-level graph below.
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

        class_method_meta: dict[str, list[FunctionInfo]] = {}
        for cls in module_classes:
            cls_id = _class_id(cls)
            methods = [
                fn_by_id[fn_id]
                for fn_id in function_ids
                if fn_id in fn_by_id
                and fn_by_id[fn_id].class_name == cls.qualname
                and fn_by_id[fn_id].module_name == cls.module_name
            ]
            methods.sort(key=lambda item: (item.line, item.id))
            class_method_meta[cls_id] = methods
            public_methods = [
                method for method in methods
                if method.visibility in {"public", "lifecycle"} and not method.is_abstract
            ]
            entry_methods = (
                [] if cls.is_abstract or cls.class_kind in {"abstract", "interface"}
                else _class_entry_methods(methods, entry_id_set)
            )
            module_nodes[cls_id] = {
                "id": cls_id,
                "kind": "class",
                "uid": cls_id,
                "name": cls.name,
                "qualifiedName": cls.qualname,
                "classKind": cls.class_kind,
                "isAbstract": cls.is_abstract,
                "bases": list(cls.bases),
                "decorators": list(cls.decorators),
                "note": cls.note,
                "file": cls.file,
                "line": cls.line,
                "endLine": cls.end_line,
                "moduleId": module_id,
                "methodCount": len(methods),
                "publicMethodIds": [method.id for method in public_methods],
                "entryMethodIds": [method.id for method in entry_methods],
                "exitMethodIds": [method.id for method in public_methods],
                "methods": [_method_summary(method, cls_id) for method in methods],
                "w": CLASS_W,
                "h": CLASS_H,
            }

        for fn_id in free_function_ids:
            fn = fn_by_id[fn_id]
            module_nodes[fn_id] = {
                "id": fn_id,
                "kind": "function",
                "uid": fn_id,
                "name": fn.name,
                "qualifiedName": f"{fn.module_name}.{fn.qualname}",
                "note": fn.note,
                "visibility": fn.visibility,
                "file": fn.file,
                "line": fn.line,
                "functionDetailId": fn_id,
                "w": FUNCTION_W,
                "h": FUNCTION_H,
            }

        provided_apis = _module_provided_apis(
            module_id,
            module_name,
            module_classes,
            class_method_meta,
            free_function_ids,
            fn_by_id,
            entry_id_set,
        )
        module_node["providedApiCount"] = len(provided_apis)

        internal_records = [
            record
            for record in calls
            if record.from_module == module_id and record.to_module == module_id
        ]

        # Canonical method-level graph, used by the future class focus view.
        method_aggregate: dict[tuple[str, str], list[CallRecord]] = defaultdict(list)
        for record in internal_records:
            method_aggregate[(record.from_function, record.to_function)].append(record)
        method_edges: list[dict[str, Any]] = []
        for edge_index, ((from_id, to_id), records) in enumerate(sorted(method_aggregate.items()), start=1):
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
            method_edges.append(
                _macro_edge(
                    _edge_id(f"module:{module_id}:method", edge_index),
                    from_id,
                    to_id,
                    primary_type=semantics["primaryType"],
                    relations=semantics["relations"],
                    role="internal",
                    evidence=evidence,
                    confidence="high" if len(records) == 1 else "medium",
                )
            )

        # Component-level aggregation for the module page.  Calls internal to
        # one class are intentionally hidden here and remain available in
        # ``methodEdges`` for the class focus view.
        component_aggregate: dict[tuple[str, str], list[CallRecord]] = defaultdict(list)
        for record in internal_records:
            source_fn = fn_by_id.get(record.from_function)
            target_fn = fn_by_id.get(record.to_function)
            if source_fn is None or target_fn is None:
                continue
            source_component = _method_component_id(source_fn)
            target_component = _method_component_id(target_fn)
            if source_component == target_component:
                continue
            component_aggregate[(source_component, target_component)].append(record)

        module_edges: list[dict[str, Any]] = []
        for edge_index, ((from_id, to_id), records) in enumerate(sorted(component_aggregate.items()), start=1):
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

        input_boundary = module_node["inputs"][0]["id"]
        output_boundary = module_node["outputs"][0]["id"]

        # Class boundaries are explicit component boundaries.  A class gets at
        # most one module input and one module output edge; abstract classes and
        # interface/protocol classes are contracts and never become runtime
        # entry points.
        for cls in module_classes:
            if cls.is_abstract or cls.class_kind in {"abstract", "interface"}:
                continue
            cls_id = _class_id(cls)
            methods = class_method_meta.get(cls_id, [])
            entry_methods = _class_entry_methods(methods, entry_id_set)
            public_methods = [
                method for method in methods
                if method.visibility in {"public", "lifecycle"} and not method.is_abstract
            ]
            if not entry_methods and not public_methods:
                continue
            via_input = [method.id for method in entry_methods] or [method.id for method in public_methods]
            via_output = [method.id for method in public_methods] or via_input
            input_edge = _macro_edge(
                _edge_id(f"module:{module_id}", len(module_edges) + 1),
                input_boundary,
                cls_id,
                primary_type="control",
                relations=["control"],
                role="module_input",
                confidence="medium" if entry_methods and len(entry_methods) < len(public_methods) else "low",
            )
            input_edge["viaMethodIds"] = via_input
            module_edges.append(input_edge)
            output_edge = _macro_edge(
                _edge_id(f"module:{module_id}", len(module_edges) + 1),
                cls_id,
                output_boundary,
                primary_type="control",
                relations=["control"],
                role="module_output",
                confidence="low",
            )
            output_edge["viaMethodIds"] = via_output
            module_edges.append(output_edge)

        # Free functions keep the old lexical boundary heuristic, but methods
        # are excluded from it.  This is deliberately narrower than the old
        # "every method without an incoming edge" logic.
        free_incoming: set[str] = set()
        for record in internal_records:
            if record.to_function in free_function_ids:
                free_incoming.add(record.to_function)
        # A module that also contains classes should not expose every public
        # helper function as a boundary.  Only configured/main/route entries
        # qualify; the old lexical fallback applies only to class-free modules.
        free_entry_ids = [
            fn_id for fn_id in free_function_ids
            if entry_reasons.get(fn_id) in {"configured", "main", "route"}
        ]
        if not free_entry_ids and not module_classes:
            free_entry_ids = [
                fn_id for fn_id in free_function_ids
                if fn_id not in free_incoming and fn_by_id[fn_id].visibility == "public"
            ]
        for fn_id in free_entry_ids:
            module_edges.append(
                _macro_edge(
                    _edge_id(f"module:{module_id}", len(module_edges) + 1),
                    input_boundary,
                    fn_id,
                    primary_type="control",
                    relations=["control"],
                    role="module_input",
                    evidence=[],
                    confidence="low",
                )
            )
        free_outgoing = {
            record.from_function
            for record in internal_records
            if record.from_function in free_function_ids
        }
        free_terminal = [
            fn_id for fn_id in free_function_ids
            if fn_id in free_entry_ids and fn_id not in free_outgoing
        ]
        for fn_id in free_terminal:
            module_edges.append(
                _macro_edge(
                    _edge_id(f"module:{module_id}", len(module_edges) + 1),
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
                "role": role,
                "providedApis": provided_apis,
                "providedApiCount": len(provided_apis),
                "nodes": [module_nodes[node_id] for node_id in sorted(module_nodes)],
                "edges": module_edges,
                "methodEdges": method_edges,
                "classCount": len(module_classes),
                "methodCount": len(method_function_ids),
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

    # The project page is a capability-card overview, not a dependency
    # network.  Cards get their own deterministic grid; dependency evidence
    # remains in projectGraph.edges for optional relation views and queries.
    project_layout = _layout_module_cards(project_module_nodes)
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

    diagnostics = list(analysis.diagnostics)
    stats = {
        "modules": len(project_module_nodes),
        "classes": len(analysis.classes),
        "functions": len(function_details),
        "methods": sum(1 for fn in analysis.functions if fn.class_name),
        "callSites": len(call_site_list),
        "resolvedCalls": sum(1 for site in call_site_list if site.resolved),
        "macroEdges": len(project_edges) + sum(len(graph["edges"]) for graph in module_graphs),
        "providedApis": sum(len(graph["providedApis"]) for graph in module_graphs),
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
        "schemaVersion": "3.1",
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
        "functionDetails": sorted(function_details, key=lambda item: item["id"]),
        "callSites": sorted(
            (site.as_dict() for site in call_site_list),
            key=lambda item: item["id"],
        ),
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
                    "role": module.get("role"),
                    "functions": sorted(module["functions"]),
                    "freeFunctions": sorted(module.get("freeFunctions", [])),
                    "classes": sorted(module.get("classes", [])),
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
                    "role": graph.get("role"),
                    "classes": sorted(
                        [
                            {
                                "id": node["id"],
                                "classKind": node.get("classKind"),
                                "isAbstract": node.get("isAbstract"),
                                "bases": node.get("bases", []),
                                "publicMethodIds": sorted(node.get("publicMethodIds", [])),
                                "entryMethodIds": sorted(node.get("entryMethodIds", [])),
                                "methods": sorted(
                                    [
                                        {
                                            "id": method.get("id"),
                                            "methodKind": method.get("methodKind"),
                                            "visibility": method.get("visibility"),
                                            "isAbstract": method.get("isAbstract"),
                                        }
                                        for method in node.get("methods", [])
                                    ],
                                    key=lambda item: item["id"] or "",
                                ),
                            }
                            for node in graph.get("nodes", [])
                            if node.get("kind") == "class"
                        ],
                        key=lambda item: item["id"],
                    ),
                    "edges": sorted(
                        [
                            {
                                "from": edge["from"],
                                "to": edge["to"],
                                "primaryType": edge["primaryType"],
                                "relations": edge["relations"],
                                "role": edge["role"],
                                "viaMethodIds": sorted(edge.get("viaMethodIds", [])),
                                "evidence": edge.get("evidence", []),
                            }
                            for edge in graph["edges"]
                        ],
                        key=lambda item: (item["from"], item["to"], item["primaryType"], item["role"]),
                    ),
                    "methodEdges": sorted(
                        [
                            {
                                "from": edge["from"],
                                "to": edge["to"],
                                "primaryType": edge["primaryType"],
                                "relations": edge["relations"],
                                "evidence": edge.get("evidence", []),
                            }
                            for edge in graph.get("methodEdges", [])
                        ],
                        key=lambda item: (item["from"], item["to"], item["primaryType"]),
                    ),
                }
                for graph in bundle["moduleGraphs"]
            ],
            key=lambda item: item["moduleId"],
        ),
        "functionDetails": sorted(
            [
                {
                    "id": detail["id"],
                    "qualifiedName": detail["qualifiedName"],
                    "ownerClassId": detail.get("ownerClassId"),
                    "methodKind": detail.get("methodKind"),
                    "visibility": detail.get("visibility"),
                    "signature": detail["signature"],
                    "returns": detail.get("returns", ""),
                    "raises": sorted(detail.get("raises", [])),
                    "note": detail.get("note", ""),
                    "sourceHash": detail["sourceHash"],
                    "callerIds": sorted(
                        caller["functionId"] for caller in detail.get("callers", [])
                    ),
                    "calleeIds": sorted(
                        callee["functionId"]
                        for callee in detail.get("callees", [])
                        if callee.get("functionId")
                    ),
                }
                for detail in bundle["functionDetails"]
            ],
            key=lambda item: item["id"],
        ),
        "callSites": sorted(
            [
                {
                    "fromFunctionId": site["fromFunctionId"],
                    "toFunctionId": site.get("toFunctionId"),
                    "file": site["file"],
                    "line": site["line"],
                    "column": site["column"],
                    "calleeText": site["calleeText"],
                    "kind": site["kind"],
                    "resolved": site["resolved"],
                    "external": site["external"],
                    "confidence": site["confidence"],
                }
                for site in bundle["callSites"]
            ],
            key=lambda item: (
                item["fromFunctionId"], item["line"], item["column"], item["calleeText"]
            ),
        ),
    }
    return _json_hash(semantic)
