"""Main-flow projection helpers.

The main flow is a curated, function-level DAG derived from static call facts,
module capability projections and explicit dispatch declarations.  It is a
read-only projection: building it must never mutate Provider Role, API
visibility, CallSite or FunctionDetail facts.
"""

from __future__ import annotations

import ast
import hashlib
import re
import shlex
from collections import defaultdict, deque
from typing import Any, Iterable

from ..config.project_config import DispatchHint
from ..model.analysis_model import AnalysisResult, FunctionInfo, ModuleInfo
from ..model.call_model import CallSite

FLOW_NODE_W = 244
FLOW_NODE_H = 140
FLOW_PROVIDER_W = 224
FLOW_PROVIDER_H = 140
FLOW_DISPATCH_W = 248
FLOW_DISPATCH_H = 140
FLOW_X_GAP = 330
FLOW_Y_GAP = 190
FLOW_PAD = 70
FLOW_MAX_NODES = 120

_DISPATCH_COMMENT = re.compile(r"#\s*archmap:dispatch\b(?P<body>.*)$", re.IGNORECASE)


def _flow_key(entrypoint_id: str) -> str:
    return hashlib.sha1(entrypoint_id.encode("utf-8")).hexdigest()[:10]


def _unparse(node: ast.AST | None, limit: int = 140) -> str:
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except Exception:
        text = type(node).__name__
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _call_key(function_id: str, line: int, column: int) -> tuple[str, int, int]:
    return function_id, line, column


def _branch_metadata(analysis: AnalysisResult) -> dict[tuple[str, int, int], dict[str, Any]]:
    """Best-effort branch labels for call sites, without building a CFG."""

    result: dict[tuple[str, int, int], dict[str, Any]] = {}

    for fn in analysis.functions:
        node = fn.node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        def record(call: ast.Call, group: str, label: str, loop_member: bool) -> None:
            result[_call_key(fn.id, int(call.lineno), int(call.col_offset) + 1)] = {
                "branchGroup": group,
                "branchLabel": label,
                "loopMember": loop_member,
            }

        def walk(stmts: list[ast.stmt], group: str = "", label: str = "", loop_depth: int = 0) -> None:
            for stmt in stmts:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(stmt, ast.If):
                    cond = _unparse(stmt.test)
                    next_group = group or f"if:{fn.id}:{stmt.lineno}"
                    walk(stmt.body, next_group, cond, loop_depth)
                    if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                        nested = stmt.orelse[0]
                        walk([nested], next_group, _unparse(nested.test), loop_depth)
                    elif stmt.orelse:
                        walk(stmt.orelse, next_group, "else", loop_depth)
                    continue
                is_loop = isinstance(stmt, (ast.For, ast.AsyncFor, ast.While))
                nested_loop = loop_depth + 1 if is_loop else loop_depth
                for child in ast.walk(stmt):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not stmt:
                        continue
                    if isinstance(child, ast.Call):
                        record(child, group, label, nested_loop > 0)
                if isinstance(stmt, ast.Try):
                    walk(stmt.body, group, label, loop_depth)
                    for handler in stmt.handlers:
                        walk(handler.body, group, "except", loop_depth)
                    walk(stmt.orelse, group, label, loop_depth)
                    walk(stmt.finalbody, group, label, loop_depth)
                elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                    walk(stmt.body, group, label, nested_loop)
                    walk(stmt.orelse, group, label, nested_loop)
                elif isinstance(stmt, ast.With):
                    walk(stmt.body, group, label, loop_depth)

        walk(list(node.body))
    return result


def _module_from_name(analysis: AnalysisResult, module_name: str) -> ModuleInfo | None:
    if not module_name:
        return None
    name = module_name.removesuffix(".py").replace("/", ".")
    direct = next((module for module in analysis.modules if module.name == name), None)
    if direct is not None:
        return direct
    tail = name.split(".")[-1]
    matches = [module for module in analysis.modules if module.name.split(".")[-1] == tail]
    return matches[0] if len(matches) == 1 else None


def _resolve_function_ref(
    analysis: AnalysisResult,
    current_module: ModuleInfo | None,
    ref: str,
) -> str | None:
    value = str(ref or "").strip()
    if not value:
        return None
    if value.startswith("fn:"):
        return value if value in analysis.function_by_id else None
    if ":" in value:
        module_part, name = value.rsplit(":", 1)
        module = _module_from_name(analysis, module_part)
        if module is not None:
            fn = module.functions.get(name)
            if fn is not None:
                return fn.id
            matches = [item for item in module.functions.values() if item.name == name]
            if len(matches) == 1:
                return matches[0].id
    if "." in value:
        module_part, name = value.rsplit(".", 1)
        module = _module_from_name(analysis, module_part)
        if module is not None:
            fn = module.functions.get(name)
            if fn is not None:
                return fn.id
    if current_module is not None:
        fn = current_module.functions.get(value)
        if fn is not None:
            return fn.id
        imported = current_module.imports.get(value)
        if imported is not None:
            target = _module_from_name(analysis, imported.module)
            if target is not None:
                fn = target.functions.get(imported.name or value)
                if fn is not None:
                    return fn.id
    matches = [fn.id for fn in analysis.functions if fn.name == value or fn.qualname == value]
    return matches[0] if len(matches) == 1 else None


def _parse_dispatch_comment(text: str) -> dict[str, Any] | None:
    match = _DISPATCH_COMMENT.search(text or "")
    if not match:
        return None
    body = match.group("body").strip()
    tokens = shlex.split(body) if body else []
    candidates: list[str] = []
    complete = False
    reason = "comment"
    for token in tokens:
        if token.startswith("candidates="):
            candidates.extend(
                item.strip()
                for item in token.removeprefix("candidates=").split(",")
                if item.strip()
            )
        elif token.startswith("complete="):
            complete = token.removeprefix("complete=").strip().lower() == "true"
        elif token.startswith("reason="):
            reason = token.removeprefix("reason=").strip() or reason
    return {
        "candidates": candidates,
        "complete": complete,
        "reason": reason,
        "source": "comment",
    }


def _description_comment(source_lines: list[str], line: int) -> str:
    for index in (line, line - 1, line - 2):
        if 1 <= index <= len(source_lines):
            text = source_lines[index - 1]
            if _DISPATCH_COMMENT.search(text):
                return text
    return ""


def _class_provider_metadata(module_graphs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for graph in module_graphs:
        module_id = str(graph.get("moduleId") or "")
        module_name = str(graph.get("name") or module_id)
        color = str(graph.get("color") or "#60a5fa")
        for node in graph.get("nodes", []):
            if node.get("kind") != "class":
                continue
            usage = node.get("usage") or {}
            constructor_id = (usage.get("constructor") or {}).get("functionId")
            if not constructor_id:
                continue
            protocol_capabilities: dict[str, dict[str, Any]] = {}
            for api in node.get("providedApis", []):
                kind = str(api.get("kind") or "")
                if kind in {"context_manager", "async_context_manager", "callable", "iterable"}:
                    protocol_capabilities[kind] = dict(api)
            result[str(constructor_id)] = {
                "kind": "provider",
                "providerId": node.get("id"),
                "providerKind": "class",
                "providerName": node.get("name") or node.get("id"),
                "providerRole": node.get("providerRole"),
                "moduleId": module_id,
                "moduleName": module_name,
                "color": color,
                "label": node.get("name") or node.get("id"),
                "signature": (usage.get("constructor") or {}).get("signature") or "",
                "note": node.get("note") or "",
                "protocols": list(usage.get("protocols") or []),
                "protocolCapabilities": protocol_capabilities,
                "w": FLOW_PROVIDER_W,
                "h": FLOW_PROVIDER_H,
            }
    return result


def _api_metadata(module_graphs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for graph in module_graphs:
        module_id = str(graph.get("moduleId") or "")
        module_name = str(graph.get("name") or module_id)
        color = str(graph.get("color") or "#60a5fa")
        for provider in graph.get("apiProviders", []):
            for api in provider.get("apis", []):
                function_id = api.get("functionId")
                if not function_id or api.get("exposure") != "public":
                    continue
                # Inherited capabilities are class-card surfaces, not a second
                # declaration of the base function.  Main-flow interface nodes
                # must retain the canonical declaring provider.
                if api.get("inherited"):
                    continue
                result[str(function_id)] = {
                    "kind": "interface",
                    "providerId": provider.get("providerId") or api.get("providerId"),
                    "providerKind": provider.get("providerKind") or api.get("providerKind"),
                    "providerName": provider.get("providerName") or api.get("providerName"),
                    "providerRole": provider.get("providerRole") or api.get("providerRole"),
                    "moduleId": module_id,
                    "moduleName": module_name,
                    "color": color,
                    "label": api.get("display") or api.get("signature") or function_id,
                    "signature": api.get("signature") or "",
                    "note": api.get("note") or "",
                    "capabilityId": api.get("id"),
                    "capabilityKind": api.get("kind"),
                    "w": FLOW_NODE_W,
                    "h": FLOW_NODE_H,
                }
    return result


def _static_dispatch_candidates(
    analysis: AnalysisResult,
    api_meta: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
    """Discover only high-signal candidate registrations.

    Returns ``(argparse_candidates, registry_candidates)``.  These are always
    treated as partial candidate sets.
    """

    argparse_candidates: list[str] = []
    registry_candidates: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for module in analysis.modules:
        for fn in module.functions.values():
            for node in ast.walk(fn.node):
                # parser.set_defaults(func=cmd_build) style registrations.
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr == "set_defaults":
                        for keyword in node.keywords:
                            if keyword.arg != "func":
                                continue
                            ref = None
                            if isinstance(keyword.value, ast.Name):
                                ref = keyword.value.id
                            elif isinstance(keyword.value, ast.Attribute):
                                ref = keyword.value.attr
                            resolved = _resolve_function_ref(analysis, module, ref or "")
                            if resolved:
                                argparse_candidates.append(resolved)
                # Static dict/list tables of function references.
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target = node.targets[0].id
                    values: list[ast.AST] = []
                    if isinstance(node.value, ast.Dict):
                        values = [value for value in node.value.values if value is not None]
                    elif isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        values = list(node.value.elts)
                    for value in values:
                        ref = None
                        if isinstance(value, ast.Name):
                            ref = value.id
                        elif isinstance(value, ast.Attribute):
                            ref = value.attr
                        resolved = _resolve_function_ref(analysis, module, ref or "")
                        if resolved:
                            registry_candidates[module.name][target].append(resolved)
    return (
        sorted(set(argparse_candidates)),
        {
            module: {name: sorted(set(values)) for name, values in tables.items()}
            for module, tables in registry_candidates.items()
        },
    )


def _is_dynamic_dispatch_site(site: CallSite) -> bool:
    if site.resolved or site.external:
        return False
    text = str(site.callee_text or "").strip()
    if text.endswith(".func"):
        return True
    if text.startswith("getattr("):
        return True
    # Calling the result of a mapping lookup, e.g. HANDLERS[command]().
    # Attribute access on a subscript (detail['id'].replace) is not a
    # dynamic callable dispatch and must not create a dispatch node.
    if text.endswith("]") and "[" in text and "]." not in text:
        return True
    return False


def _resolve_hint_candidates(
    analysis: AnalysisResult,
    module: ModuleInfo | None,
    candidates: list[str],
    diagnostics: list[dict[str, Any]],
    *,
    expression: str,
) -> list[str]:
    resolved: list[str] = []
    for candidate in candidates:
        function_id = _resolve_function_ref(analysis, module, candidate)
        if function_id:
            resolved.append(function_id)
        else:
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": "DISPATCH_CANDIDATE_UNRESOLVED",
                    "message": f"dispatch candidate {candidate!r} for {expression or '<unknown>'} could not be resolved",
                }
            )
    return sorted(set(resolved))


def _node_meta_for_target(
    target_id: str,
    fn: FunctionInfo | None,
    *,
    main_module_id: str,
    api_meta: dict[str, dict[str, Any]],
    class_meta: dict[str, dict[str, Any]],
    module_name_by_id: dict[str, str],
    color_by_module: dict[str, str],
    usage_kind: str = "",
) -> dict[str, Any] | None:
    if target_id in class_meta:
        meta = dict(class_meta[target_id])
        capability = (meta.get("protocolCapabilities") or {}).get(usage_kind)
        if capability is not None:
            meta.update(
                {
                    "capabilityId": capability.get("id"),
                    "capabilityKind": capability.get("kind") or usage_kind,
                    "label": (
                        capability.get("display")
                        or capability.get("signature")
                        or meta.get("label")
                    ),
                    "signature": capability.get("signature") or meta.get("signature") or "",
                    "protocols": sorted(
                        set(meta.get("protocols") or [])
                        | {str(capability.get("kind") or usage_kind)}
                    ),
                    "usageKind": usage_kind,
                }
            )
        meta.pop("protocolCapabilities", None)
        return meta
    if fn is None:
        return None
    # Main-module orchestration functions keep their flow identity even when
    # they are also exposed as module APIs (server/client, command helpers).
    if fn.module_id == main_module_id and not fn.name.startswith("_"):
        if fn.method_kind in {"constructor", "dunder"}:
            return None
        return {
            "kind": "orchestrator",
            "providerId": target_id,
            "providerKind": "function" if not fn.class_name else "class",
            "providerName": fn.name,
            "providerRole": None,
            "moduleId": fn.module_id,
            "moduleName": module_name_by_id.get(fn.module_id, fn.module_id),
            "color": color_by_module.get(fn.module_id, "#f59e0b"),
            "label": f"{fn.name}()",
            "signature": fn.signature,
            "note": fn.note,
            "w": FLOW_NODE_W,
            "h": FLOW_NODE_H,
        }
    if target_id in api_meta:
        return dict(api_meta[target_id])
    return None


def _edge_path(from_node: dict[str, Any], to_node: dict[str, Any]) -> str:
    sx = from_node["x"] + from_node["w"]
    sy = from_node["y"] + from_node["h"] / 2
    tx = to_node["x"]
    ty = to_node["y"] + to_node["h"] / 2
    if tx < sx:
        sx = from_node["x"]
        tx = to_node["x"] + to_node["w"]
    bend = max(60.0, min(180.0, abs(tx - sx) * 0.46))
    sign = 1 if tx >= sx else -1
    return (
        f"M {round(sx, 2)} {round(sy, 2)} "
        f"C {round(sx + sign * bend, 2)} {round(sy, 2)} "
        f"{round(tx - sign * bend, 2)} {round(ty, 2)} "
        f"{round(tx, 2)} {round(ty, 2)}"
    )


def _layout_flow(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]], flow_id: str
) -> dict[str, Any]:
    by_id = {node["id"]: node for node in nodes}
    node_order = {node["id"]: index for index, node in enumerate(nodes)}
    predecessors: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if source in by_id and target in by_id and source != target:
            predecessors[target].append(source)

    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def rank(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            return 0
        visiting.add(node_id)
        value = max((rank(parent) + 1 for parent in predecessors.get(node_id, [])), default=0)
        visiting.discard(node_id)
        memo[node_id] = value
        return value

    ranks = {node_id: rank(node_id) for node_id in by_id}
    groups: dict[int, list[str]] = defaultdict(list)
    for node_id, value in ranks.items():
        groups[value].append(node_id)

    positions: dict[str, dict[str, Any]] = {}
    placed_y: dict[str, float] = {}
    max_rows = max((len(group) for group in groups.values()), default=1)
    row_span = max(0.0, (max_rows - 1) * FLOW_Y_GAP)

    for value in sorted(groups):
        group = list(groups[value])
        if value == 0:
            group.sort(key=lambda node_id: (node_order.get(node_id, 0), node_id))
        else:
            def barycenter(node_id: str) -> float:
                parent_y = [
                    placed_y[parent]
                    for parent in predecessors.get(node_id, [])
                    if parent in placed_y
                ]
                return sum(parent_y) / len(parent_y) if parent_y else float("inf")

            group.sort(
                key=lambda node_id: (
                    barycenter(node_id),
                    node_order.get(node_id, 0),
                    node_id,
                )
            )

        group_span = max(0.0, (len(group) - 1) * FLOW_Y_GAP)
        start_y = FLOW_PAD + (row_span - group_span) / 2
        for index, node_id in enumerate(group):
            node = by_id[node_id]
            y = round(start_y + index * FLOW_Y_GAP, 2)
            positions[node_id] = {
                "x": round(FLOW_PAD + value * FLOW_X_GAP, 2),
                "y": y,
                "w": node.get("w", FLOW_NODE_W),
                "h": node.get("h", FLOW_NODE_H),
            }
            placed_y[node_id] = y

    max_x = max((item["x"] + item["w"] for item in positions.values()), default=400)
    max_y = max((item["y"] + item["h"] for item in positions.values()), default=300)
    layout_edges: dict[str, Any] = {}
    for edge in edges:
        source = positions.get(edge.get("from"))
        target = positions.get(edge.get("to"))
        if source is None or target is None:
            continue
        layout_edges[edge["id"]] = {"d": _edge_path(source, target)}
    return {
        "mode": "main-flow",
        "canvas": {
            "width": round(max_x + FLOW_PAD, 2),
            "height": round(max_y + FLOW_PAD, 2),
            "padding": FLOW_PAD,
        },
        "nodes": positions,
        "edges": layout_edges,
        "ranks": ranks,
        "flowId": flow_id,
    }


def build_main_flows(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    entrypoints: list[dict[str, Any]],
    module_graphs: list[dict[str, Any]],
    dispatch_hints: list[DispatchHint] | None = None,
) -> tuple[list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    """Build main-flow DAGs for every entrypoint."""

    diagnostics: list[dict[str, Any]] = []
    if not entrypoints:
        return [], None, diagnostics
    fn_by_id = analysis.function_by_id
    call_list = list(call_sites)
    calls_by_from: dict[str, list[CallSite]] = defaultdict(list)
    for site in call_list:
        calls_by_from[site.from_function_id].append(site)
    for sites in calls_by_from.values():
        sites.sort(key=lambda item: (item.line, item.column, item.callee_text, item.id))

    module_by_id = {module.module_id: module for module in analysis.modules}
    module_graph_by_id = {str(graph.get("moduleId")): graph for graph in module_graphs}
    main_module_id = analysis.config.main_module_id
    if main_module_id not in module_graph_by_id:
        main_module_id = next(
            (str(graph.get("moduleId")) for graph in module_graphs if graph.get("moduleKind") == "main"),
            next(iter(module_graph_by_id), ""),
        )
    module_name_by_id = {
        str(graph.get("moduleId")): str(graph.get("name") or graph.get("moduleId") or "")
        for graph in module_graphs
    }
    color_by_module = {
        str(graph.get("moduleId")): str(graph.get("color") or "#60a5fa")
        for graph in module_graphs
    }
    api_meta = _api_metadata(module_graphs)
    class_meta = _class_provider_metadata(module_graphs)
    argparse_candidates, registry_candidates = _static_dispatch_candidates(analysis, api_meta)
    branch_info = _branch_metadata(analysis)
    hints = list(dispatch_hints or [])
    flows: list[dict[str, Any]] = []

    for entry_index, entry in enumerate(entrypoints):
        entry_id = str(entry.get("functionId") or "")
        if entry_id not in fn_by_id:
            continue
        flow_key = _flow_key(entry_id)
        flow_id = f"main-flow:{entry_index + 1}:{flow_key}"
        nodes_by_id: dict[str, dict[str, Any]] = {}
        node_order: list[str] = []
        edge_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        expanded: set[str] = set()
        hidden_seen: set[tuple[str, str]] = set()
        truncated = False

        def ensure_node(
            function_id: str,
            meta: dict[str, Any] | None = None,
            *,
            force_kind: str | None = None,
            usage_kind: str = "",
        ) -> dict[str, Any] | None:
            fn = fn_by_id.get(function_id)
            resolved_meta = meta or _node_meta_for_target(
                function_id,
                fn,
                main_module_id=main_module_id,
                api_meta=api_meta,
                class_meta=class_meta,
                module_name_by_id=module_name_by_id,
                color_by_module=color_by_module,
                usage_kind=usage_kind,
            )
            if resolved_meta is None and function_id not in fn_by_id:
                return None
            resolved_meta = dict(resolved_meta or {})
            kind = force_kind or resolved_meta.get("kind") or "orchestrator"
            key = (
                "provider" if kind == "provider" and resolved_meta.get("providerId")
                else "interface" if kind == "interface" and resolved_meta.get("capabilityId")
                else "function"
            )
            identity = (
                resolved_meta.get("providerId")
                if kind == "provider" and resolved_meta.get("providerId")
                else resolved_meta.get("capabilityId")
                if kind == "interface" and resolved_meta.get("capabilityId")
                else function_id
            )
            node_id = f"flow:{flow_key}:{key}:{identity}"
            existing = nodes_by_id.get(node_id)
            if existing is not None:
                return existing
            node = {
                "id": node_id,
                "kind": "entry" if function_id == entry_id else kind,
                "flowRole": "entry" if function_id == entry_id else (
                    "dispatch" if kind == "dispatch"
                    else "provider" if kind == "provider"
                    else "interface" if kind == "interface"
                    else "function"
                ),
                "functionId": function_id,
                "providerId": resolved_meta.get("providerId") or function_id,
                "providerKind": resolved_meta.get("providerKind") or "function",
                "providerName": resolved_meta.get("providerName") or (fn.name if fn else function_id),
                "providerRole": resolved_meta.get("providerRole"),
                "moduleId": resolved_meta.get("moduleId") or (fn.module_id if fn else ""),
                "moduleName": resolved_meta.get("moduleName") or module_name_by_id.get(fn.module_id if fn else "", ""),
                "color": resolved_meta.get("color") or color_by_module.get(fn.module_id if fn else "", "#60a5fa"),
                "label": resolved_meta.get("label") or (f"{fn.name}()" if fn else function_id),
                "signature": resolved_meta.get("signature") or (fn.signature if fn else ""),
                "note": resolved_meta.get("note") or (fn.note if fn else ""),
                "capabilityId": resolved_meta.get("capabilityId"),
                "capabilityKind": resolved_meta.get("capabilityKind"),
                "protocols": list(resolved_meta.get("protocols") or []),
                "usageKind": resolved_meta.get("usageKind") or "",
                "isEntry": function_id == entry_id,
                "flowBoundary": bool(
                    resolved_meta.get("moduleId")
                    and resolved_meta.get("moduleId") != main_module_id
                    and kind in {"interface", "provider"}
                ),
                "expandable": kind in {"entry", "orchestrator"},
                "w": resolved_meta.get("w") or FLOW_NODE_W,
                "h": resolved_meta.get("h") or FLOW_NODE_H,
            }
            nodes_by_id[node_id] = node
            node_order.append(node_id)
            return node

        def add_edge(
            from_node: dict[str, Any],
            to_node: dict[str, Any],
            *,
            kind: str,
            confidence: str,
            evidence: list[dict[str, Any]],
            branch_group: str = "",
            branch_label: str = "",
            via_function_ids: list[str] | None = None,
            reason: str = "",
            candidate_source: str = "",
        ) -> None:
            if from_node["id"] == to_node["id"]:
                return
            key = (from_node["id"], to_node["id"], kind, branch_group)
            edge = edge_by_key.get(key)
            if edge is None:
                edge = {
                    "id": f"flow-edge:{flow_key}:{len(edge_by_key) + 1}",
                    "from": from_node["id"],
                    "to": to_node["id"],
                    "kind": kind,
                    "primaryType": "call",
                    "relations": ["call"],
                    "role": "main_flow",
                    "confidence": confidence,
                    "evidence": [],
                    "viaFunctionIds": sorted(set(via_function_ids or [])),
                    "branchGroup": branch_group,
                    "branchLabel": branch_label,
                    "reason": reason,
                    "candidateSource": candidate_source,
                    "dashed": kind == "composition",
                }
                edge_by_key[key] = edge
            known = {item.get("callSiteId") for item in edge["evidence"]}
            for item in evidence:
                if item.get("callSiteId") not in known:
                    edge["evidence"].append(item)
            if edge["evidence"]:
                edge["relations"] = ["call", "data"] if any(item.get("argumentCount", 0) for item in edge["evidence"]) else ["call"]
            if edge["kind"] == "call_path":
                edge["relations"] = sorted(set(edge["relations"]) | {"call"})

        entry_fn = fn_by_id[entry_id]
        entry_node = ensure_node(entry_id, force_kind="entry")
        if entry_node is None:
            continue
        queue: deque[tuple[str, str, list[CallSite], list[str]]] = deque([(entry_id, entry_node["id"], [], [])])
        while queue:
            function_id, ancestor_node_id, trail, via_ids = queue.popleft()
            fn = fn_by_id.get(function_id)
            if fn is None:
                continue
            source_node = nodes_by_id.get(ancestor_node_id)
            if source_node is None:
                continue
            unresolved_index = 0
            for site in calls_by_from.get(function_id, []):
                if len(nodes_by_id) >= FLOW_MAX_NODES:
                    truncated = True
                    break
                branch = branch_info.get(_call_key(fn.id, site.line, site.column), {})
                is_dispatch = _is_dynamic_dispatch_site(site) or bool(site.polymorphic)
                if not site.resolved or not site.to_function_id:
                    if not is_dispatch:
                        continue
                    unresolved_index += 1
                    module = module_by_id.get(fn.module_id)
                    comment = _parse_dispatch_comment(
                        _description_comment(module.lines if module else [], site.line)
                    )
                    matching_hints = [
                        hint for hint in hints
                        if _resolve_function_ref(analysis, module, hint.function) == fn.id
                        and (not hint.expression or hint.expression == site.callee_text)
                    ]
                    hint = matching_hints[min(unresolved_index - 1, len(matching_hints) - 1)] if matching_hints else None
                    declared_complete = bool(hint and hint.complete) or bool(comment and comment.get("complete"))
                    candidates: list[str] = []
                    candidate_source = "unknown"
                    reason = "dynamic_dispatch"
                    if site.polymorphic:
                        candidates.extend(site.candidates)
                        candidate_source = "polymorphic"
                        reason = "polymorphic_dispatch"
                    if hint and hint.candidates:
                        candidates.extend(
                            _resolve_hint_candidates(
                                analysis, module, hint.candidates, diagnostics,
                                expression=site.callee_text,
                            )
                        )
                        candidate_source = "config"
                        reason = hint.reason or reason
                    if comment and comment.get("candidates"):
                        candidates.extend(
                            _resolve_hint_candidates(
                                analysis, module, comment["candidates"], diagnostics,
                                expression=site.callee_text,
                            )
                        )
                        candidate_source = "comment" if candidate_source == "unknown" else candidate_source
                        reason = comment.get("reason") or reason
                    if not declared_complete and not site.polymorphic:
                        static_candidates: list[str] = []
                        if site.callee_text.endswith(".func"):
                            static_candidates.extend(argparse_candidates)
                            if static_candidates:
                                candidate_source = "argparse_registry" if candidate_source == "unknown" else candidate_source
                        registry = registry_candidates.get(fn.module_name, {})
                        for name, values in registry.items():
                            if site.callee_text.startswith(f"{name}["):
                                static_candidates.extend(values)
                                candidate_source = "static_registry" if candidate_source == "unknown" else candidate_source
                        candidates.extend(static_candidates)
                    candidates = sorted(set(candidates))
                    dispatch_node_id = f"flow:{flow_key}:dispatch:{site.id}"
                    dispatch_node = nodes_by_id.get(dispatch_node_id)
                    if dispatch_node is None:
                        dispatch_node = {
                            "id": dispatch_node_id,
                            "kind": "dispatch",
                            "flowRole": "dispatch",
                            "label": site.callee_text,
                            "expression": site.callee_text,
                            "callSiteId": site.id,
                            "moduleId": fn.module_id,
                            "moduleName": module_name_by_id.get(fn.module_id, fn.module_id),
                            "color": color_by_module.get(fn.module_id, "#60a5fa"),
                            "candidateCount": len(candidates),
                            "candidateSetComplete": declared_complete,
                            "candidateSource": candidate_source,
                            "unresolvedReason": None if candidates else "dynamic_callable_not_inferable",
                            "note": "动态分发边界；候选连线使用低置信度 composition 语义。",
                            "w": FLOW_DISPATCH_W,
                            "h": FLOW_DISPATCH_H,
                        }
                        nodes_by_id[dispatch_node_id] = dispatch_node
                        node_order.append(dispatch_node_id)
                    evidence = [
                        {
                            "callSiteId": item.id,
                            "fromFunctionId": item.from_function_id,
                            "toFunctionId": item.to_function_id,
                            "file": item.file,
                            "line": item.line,
                            "argumentCount": item.argument_count,
                            "callText": item.call_text,
                            "usageKind": item.usage_kind,
                        }
                        for item in [*trail, site]
                    ]
                    add_edge(
                        source_node,
                        dispatch_node,
                        kind="call_path" if trail else "call",
                        confidence="medium" if trail else "high",
                        evidence=evidence,
                        branch_group=branch.get("branchGroup", ""),
                        branch_label=branch.get("branchLabel", ""),
                        via_function_ids=via_ids,
                    )
                    for candidate_id in candidates:
                        candidate_fn = fn_by_id.get(candidate_id)
                        candidate_meta = _node_meta_for_target(
                            candidate_id,
                            candidate_fn,
                            main_module_id=main_module_id,
                            api_meta=api_meta,
                            class_meta=class_meta,
                            module_name_by_id=module_name_by_id,
                            color_by_module=color_by_module,
                            usage_kind=site.usage_kind,
                        )
                        candidate_node = ensure_node(
                            candidate_id, candidate_meta, usage_kind=site.usage_kind
                        )
                        if candidate_node is None:
                            continue
                        add_edge(
                            dispatch_node,
                            candidate_node,
                            kind="composition",
                            confidence="low",
                            evidence=[],
                            branch_group=f"dispatch:{site.id}",
                            branch_label=site.callee_text,
                            reason=reason,
                            candidate_source=candidate_source,
                        )
                        if candidate_node.get("expandable") and candidate_id not in expanded:
                            expanded.add(candidate_id)
                            queue.append((candidate_id, candidate_node["id"], [], []))
                    continue

                target_id = str(site.to_function_id)
                target_fn = fn_by_id.get(target_id)
                target_meta = _node_meta_for_target(
                    target_id,
                    target_fn,
                    main_module_id=main_module_id,
                    api_meta=api_meta,
                    class_meta=class_meta,
                    module_name_by_id=module_name_by_id,
                    color_by_module=color_by_module,
                    usage_kind=site.usage_kind,
                )
                evidence = [
                    {
                        "callSiteId": item.id,
                        "fromFunctionId": item.from_function_id,
                        "toFunctionId": item.to_function_id,
                        "file": item.file,
                        "line": item.line,
                        "argumentCount": item.argument_count,
                        "callText": item.call_text,
                        "usageKind": item.usage_kind,
                    }
                    for item in [*trail, site]
                ]
                if target_meta is not None:
                    target_node = ensure_node(target_id, target_meta, usage_kind=site.usage_kind)
                    if target_node is None:
                        continue
                    add_edge(
                        source_node,
                        target_node,
                        kind="call_path" if trail else "call",
                        confidence="medium" if trail else "high",
                        evidence=evidence,
                        branch_group=branch.get("branchGroup", ""),
                        branch_label=branch.get("branchLabel", ""),
                        via_function_ids=via_ids,
                    )
                    if target_node.get("expandable") and target_id not in expanded:
                        expanded.add(target_id)
                        queue.append((target_id, target_node["id"], [], []))
                else:
                    # The main flow is a bounded composition projection.  Only
                    # hidden implementation functions inside the main module may
                    # be traversed.  Functional-module internals are deliberately
                    # opaque at this layer and remain available through module
                    # pages, Method Detail and later trace/impact views.
                    if target_fn is None or target_fn.module_id != main_module_id:
                        continue
                    state_key = (target_id, ancestor_node_id)
                    if state_key in hidden_seen:
                        continue
                    hidden_seen.add(state_key)
                    queue.append((target_id, ancestor_node_id, [*trail, site], [*via_ids, target_id]))
            if truncated:
                break

        flow_nodes = [nodes_by_id[node_id] for node_id in node_order]
        for index, node in enumerate(flow_nodes):
            node["order"] = index
        flow_edges = list(edge_by_key.values())
        layout = _layout_flow(flow_nodes, flow_edges, flow_id)
        entry_node = nodes_by_id[entry_node["id"]]
        flows.append(
            {
                "kind": "archmap.main-flow",
                "id": flow_id,
                "moduleId": main_module_id,
                "entrypointId": entry_id,
                "entrypointReason": entry.get("reason") or "heuristic",
                "name": entry_node.get("label") or entry_id,
                "nodes": flow_nodes,
                "edges": flow_edges,
                "nodeCount": len(flow_nodes),
                "edgeCount": len(flow_edges),
                "truncated": truncated,
                "layout": layout,
            }
        )

    primary_flow_id = flows[0]["id"] if flows else None
    return flows, primary_flow_id, diagnostics
