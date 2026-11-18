"""Deterministic horizontal execution-flow layout for P5.

The graph uses a left-to-right main spine.  Branch and multi-branch arms fan
vertically; loops expose a ``loop_body`` port without drawing a back lane.
Edges are cubic curves and every edge stores the source/target port names so the
browser can reroute incident curves while a card is dragged.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

PAD = 64.0
X_GAP = 78.0
Y_GAP = 46.0
LANE_GAP = 48.0
LANE_STEP = 18.0


def _node_size(node: dict[str, Any]) -> tuple[float, float]:
    kind = str(node.get("kind") or "")
    if kind == "multi_branch":
        cases = len(node.get("cases") or [])
        return 300.0, max(168.0, 122.0 + cases * 28.0)
    if kind == "dispatch":
        return 300.0, 190.0
    if kind in {"free_function", "interface", "branch"}:
        return 300.0, 160.0
    if kind == "loop":
        return 300.0, 186.0
    if kind in {"break", "continue", "return"}:
        return 250.0, 128.0
    if kind in {"entry", "exit"}:
        return 260.0, 128.0
    return 280.0, 156.0


def _port_specs(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return relative port anchors and display metadata for a node.

    P5.1 renders ports as ordinary in-card rows.  These coordinates are the
    deterministic fallback used before the browser measures the real DOM row
    centers; the browser recalibrates edge endpoints after rendering and while
    dragging.
    """

    kind = str(node.get("kind") or "")
    w = float(node.get("w") or 0)
    h = float(node.get("h") or 0)

    def row_y(index: int, *, first: float = 105.5, step: float = 28.0) -> float:
        return min(h - 12.0, first + index * step)

    ports: dict[str, dict[str, Any]] = {
        "in": {"x": 0.0, "y": h * 0.5, "side": "left", "shape": "triangle", "label": ""},
    }
    if kind == "entry":
        return {
            "out": {"x": w, "y": row_y(0), "side": "right", "shape": "triangle", "label": "开始"},
        }
    if kind == "exit":
        return {
            "in": {"x": 0.0, "y": row_y(0), "side": "left", "shape": "triangle", "label": "进入"},
        }
    if kind in {"break", "continue", "return"}:
        return {
            "in": {"x": 0.0, "y": row_y(0), "side": "left", "shape": "triangle", "label": "进入"},
        }
    if kind == "branch":
        return {
            "in": {"x": 0.0, "y": row_y(0), "side": "left", "shape": "triangle", "label": "进入分支"},
            "true": {"x": w, "y": row_y(0), "side": "right", "shape": "circle", "label": "是"},
            "false": {"x": w, "y": row_y(1), "side": "right", "shape": "circle", "label": "否"},
        }
    if kind == "multi_branch":
        cases = list(node.get("cases") or [])
        ports: dict[str, dict[str, Any]] = {
            "in": {"x": 0.0, "y": row_y(0), "side": "left", "shape": "triangle", "label": "进入分支"},
        }
        for index, case in enumerate(cases):
            ports[f"case:{index}"] = {
                "x": w,
                "y": row_y(index),
                "side": "right",
                "shape": "circle",
                "label": str(case.get("label") or case.get("key") or f"case {index + 1}"),
                "caseIndex": index,
            }
        ports["default"] = {
            "x": w,
            "y": row_y(len(cases)),
            "side": "right",
            "shape": "diamond",
            "label": "默认",
        }
        return ports
    if kind == "loop":
        return {
            "in": {"x": 0.0, "y": row_y(0), "side": "left", "shape": "triangle", "label": "进入循环"},
            "loop_body": {"x": w, "y": row_y(0), "side": "right", "shape": "triangle", "label": "循环体"},
            "loop_complete": {"x": w, "y": row_y(1), "side": "right", "shape": "triangle", "label": "离开循环"},
        }
    if kind == "dispatch":
        return {
            "in": {"x": 0.0, "y": row_y(0), "side": "left", "shape": "triangle", "label": "进入"},
            "out": {"x": w, "y": row_y(1), "side": "right", "shape": "triangle", "label": "分发"},
        }
    ports["out"] = {"x": w, "y": row_y(0), "side": "right", "shape": "triangle", "label": "返回"}
    return ports


def _rank_nodes(
    node_ids: list[str],
    edges: list[dict[str, Any]],
    entry_id: str,
) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source not in indegree or target not in indegree or source == target:
            continue
        outgoing[source].append(target)
        indegree[target] += 1
    queue = deque(sorted((node_id for node_id in node_ids if indegree[node_id] == 0), key=node_ids.index))
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in outgoing.get(node_id, []):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(node_ids):
        order = list(node_ids)
    rank = {node_id: 0 for node_id in node_ids}
    for node_id in order:
        for target in outgoing.get(node_id, []):
            rank[target] = max(rank[target], rank[node_id] + 1)
    if entry_id in rank:
        rank[entry_id] = 0
    return rank


def _port_for_edge(edge: dict[str, Any], source: dict[str, Any], outgoing_same_source: list[dict[str, Any]]) -> str:
    kind = str(edge.get("kind") or "")
    if kind in {"true", "false", "loop_body", "loop_complete"}:
        return kind
    if kind == "default":
        return "default"
    if kind == "case":
        controls = [item for item in outgoing_same_source if item.get("kind") == "case"]
        index = controls.index(edge) if edge in controls else 0
        return f"case:{index}"
    return "out"


def _curve_path(
    sx: float,
    sy: float,
    tx: float,
    ty: float,
    *,
    lane_y: float | None = None,
) -> str:
    if lane_y is None:
        bend = max(42.0, min(210.0, abs(tx - sx) * 0.46))
        c1x = sx + bend
        c2x = tx - bend
        return f"M {sx:.2f} {sy:.2f} C {c1x:.2f} {sy:.2f} {c2x:.2f} {ty:.2f} {tx:.2f} {ty:.2f}"
    # Long forward edges use a smooth two-curve lane.  This is not a loop back
    # lane; it only prevents a long loop-complete/break edge from crossing the
    # main spine cards.
    left = sx + 34.0
    right = tx - 34.0
    if right <= left:
        right = left + 18.0
    return (
        f"M {sx:.2f} {sy:.2f} "
        f"C {left:.2f} {sy:.2f} {left:.2f} {lane_y:.2f} {left + 32.0:.2f} {lane_y:.2f} "
        f"L {right - 32.0:.2f} {lane_y:.2f} "
        f"C {right:.2f} {lane_y:.2f} {right:.2f} {ty:.2f} {tx:.2f} {ty:.2f}"
    )


def layout_execution_flow(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    flow_id: str,
) -> dict[str, Any]:
    """Lay out a bounded execution flow left-to-right with curved edges."""

    if not nodes:
        return {
            "mode": "execution-flow",
            "canvas": {"width": 760.0, "height": 420.0, "padding": PAD},
            "nodes": {},
            "edges": {},
            "flowId": flow_id,
        }
    by_id = {str(node["id"]): node for node in nodes}
    node_ids = list(by_id)
    for node in nodes:
        w, h = _node_size(node)
        node["w"] = w
        node["h"] = h
    entry_id = next((node_id for node_id in node_ids if by_id[node_id].get("kind") == "entry"), node_ids[0])
    ranks = _rank_nodes(node_ids, edges, entry_id)
    groups: dict[int, list[str]] = defaultdict(list)
    for node_id in node_ids:
        groups[ranks[node_id]].append(node_id)

    edge_order = {str(edge.get("id")): index for index, edge in enumerate(edges)}
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source in by_id and target in by_id:
            incoming[target].append(edge)

    rank_widths: dict[int, float] = {}
    rank_heights: dict[int, float] = {}
    for rank_value in sorted(groups):
        group = groups[rank_value]
        if rank_value == 0:
            group.sort(key=node_ids.index)
        else:
            group.sort(key=lambda node_id: (
                min((edge_order.get(str(edge.get("id")), 10_000) for edge in incoming.get(node_id, [])), default=10_000),
                node_ids.index(node_id),
            ))
        rank_widths[rank_value] = max(float(by_id[node_id]["w"]) for node_id in group)
        rank_heights[rank_value] = (
            sum(float(by_id[node_id]["h"]) for node_id in group)
            + Y_GAP * max(0, len(group) - 1)
        )
    max_height = max(rank_heights.values(), default=0.0)

    positions: dict[str, dict[str, Any]] = {}
    cursor_x = PAD
    for rank_value in sorted(groups):
        group = groups[rank_value]
        group_height = rank_heights[rank_value]
        cursor_y = PAD + (max_height - group_height) / 2.0
        for node_id in group:
            node = by_id[node_id]
            positions[node_id] = {
                "x": round(cursor_x, 2),
                "y": round(cursor_y, 2),
                "w": float(node["w"]),
                "h": float(node["h"]),
            }
            cursor_y += float(node["h"]) + Y_GAP
        cursor_x += rank_widths[rank_value] + X_GAP

    for node_id, position in positions.items():
        by_id[node_id]["x"] = position["x"]
        by_id[node_id]["y"] = position["y"]
        by_id[node_id]["w"] = position["w"]
        by_id[node_id]["h"] = position["h"]
        port_specs = _port_specs(by_id[node_id])
        positions[node_id]["ports"] = port_specs

    max_x = max(position["x"] + position["w"] for position in positions.values())
    max_y = max(position["y"] + position["h"] for position in positions.values())
    bottom_lane = max_y + LANE_GAP

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        outgoing[str(edge.get("from") or "")].append(edge)
    lane_count = 0
    edge_layout: dict[str, dict[str, Any]] = {}
    for edge in edges:
        source_id = str(edge.get("from") or "")
        target_id = str(edge.get("to") or "")
        source = positions.get(source_id)
        target = positions.get(target_id)
        if source is None or target is None:
            continue
        source_ports = source.get("ports") or {}
        target_ports = target.get("ports") or {}
        from_port = _port_for_edge(edge, by_id[source_id], outgoing.get(source_id, []))
        if from_port not in source_ports and "out" in source_ports:
            from_port = "out"
        to_port = "in"
        if to_port not in target_ports:
            to_port = next(iter(target_ports), "in")
        from_spec = source_ports.get(from_port) or {"x": float(source["w"]), "y": float(source["h"]) * 0.5}
        to_spec = target_ports.get(to_port) or {"x": 0.0, "y": float(target["h"]) * 0.5}
        sx = float(source["x"]) + float(from_spec.get("x", 0))
        sy = float(source["y"]) + float(from_spec.get("y", 0))
        tx = float(target["x"]) + float(to_spec.get("x", 0))
        ty = float(target["y"]) + float(to_spec.get("y", 0))
        long_forward = tx - sx > 620.0 or (
            str(edge.get("kind") or "") == "loop_complete" and tx - sx > 360.0
        )
        lane_y = None
        if long_forward:
            lane_y = bottom_lane + lane_count * LANE_STEP
            lane_count += 1
        edge_layout[str(edge.get("id"))] = {
            "d": _curve_path(sx, sy, tx, ty, lane_y=lane_y),
            "fromPort": from_port,
            "toPort": to_port,
            "labelX": round(sx + 12.0, 2),
            "labelY": round(sy - 12.0, 2),
            "kind": str(edge.get("kind") or "next"),
            "text": str(edge.get("label") or ""),
            "laneY": lane_y,
        }

    canvas_bottom = max(bottom_lane + max(0, lane_count - 1) * LANE_STEP, max_y)
    return {
        "mode": "execution-flow",
        "canvas": {
            "width": round(max_x + PAD, 2),
            "height": round(canvas_bottom + PAD, 2),
            "padding": PAD,
        },
        "nodes": positions,
        "edges": edge_layout,
        "ranks": ranks,
        "flowId": flow_id,
    }
