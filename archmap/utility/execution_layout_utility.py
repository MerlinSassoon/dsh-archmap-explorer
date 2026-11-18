"""Deterministic compact top-to-bottom layout for bounded execution flows."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

PAD = 64.0
X_GAP = 58.0
Y_GAP = 24.0
LANE_GAP = 38.0
LANE_STEP = 22.0
_NON_RANK_KINDS = {"back", "continue"}


def _node_size(node: dict[str, Any]) -> tuple[float, float]:
    kind = str(node.get("kind") or "")
    if kind == "multi_branch":
        cases = len(node.get("cases") or [])
        return 250.0, max(62.0, 44.0 + cases * 18.0)
    if kind in {"entry", "free_function", "interface", "dispatch"}:
        return 232.0, 58.0
    if kind in {"branch", "loop"}:
        return 232.0, 62.0
    if kind in {"break", "continue"}:
        return 88.0, 34.0
    if kind == "return":
        return 130.0, 40.0
    if kind == "merge":
        return 56.0, 20.0
    if kind == "exit":
        return 110.0, 38.0
    return 160.0, 52.0


def _rank_nodes(
    node_ids: list[str],
    edges: list[dict[str, Any]],
    entry_id: str,
) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        kind = str(edge.get("kind") or "")
        if kind in _NON_RANK_KINDS:
            continue
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


def _source_point(
    node: dict[str, Any],
    edge: dict[str, Any],
    outgoing_same_source: list[dict[str, Any]],
) -> tuple[float, float]:
    kind = str(edge.get("kind") or "")
    x = float(node["x"])
    y = float(node["y"])
    w = float(node["w"])
    h = float(node["h"])
    if kind == "true":
        return x + w * 0.30, y + h
    if kind == "false":
        return x + w * 0.70, y + h
    if kind in {"case", "default"}:
        controls = [item for item in outgoing_same_source if item.get("kind") in {"case", "default"}]
        index = controls.index(edge) if edge in controls else 0
        count = max(1, len(controls))
        ratio = 0.5 if count == 1 else 0.14 + 0.72 * index / (count - 1)
        return x + w * ratio, y + h
    if kind == "loop_body":
        return x + w * 0.44, y + h
    if kind == "loop_complete":
        return x + w, y + h * 0.50
    return x + w * 0.50, y + h


def _target_point(node: dict[str, Any], edge: dict[str, Any]) -> tuple[float, float]:
    kind = str(edge.get("kind") or "")
    x = float(node["x"])
    y = float(node["y"])
    w = float(node["w"])
    h = float(node["h"])
    if kind in {"back", "continue"}:
        return x, y + h * 0.50
    return x + w * 0.50, y


def _orth_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    parts = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.2f} {y:.2f}")
    return " ".join(parts)


def layout_execution_flow(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    flow_id: str,
) -> dict[str, Any]:
    """Lay out a bounded execution flow top-to-bottom with control lanes."""

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

    positions: dict[str, dict[str, float]] = {}
    current_y = PAD
    for rank_value in sorted(groups):
        group = groups[rank_value]
        if rank_value == 0:
            group.sort(key=node_ids.index)
        else:
            group.sort(key=lambda node_id: (
                min((edge_order.get(str(edge.get("id")), 10_000) for edge in incoming.get(node_id, [])), default=10_000),
                node_ids.index(node_id),
            ))
        total_width = sum(float(by_id[node_id]["w"]) for node_id in group) + X_GAP * max(0, len(group) - 1)
        cursor_x = -total_width / 2.0
        row_height = max(float(by_id[node_id]["h"]) for node_id in group)
        for node_id in group:
            node = by_id[node_id]
            positions[node_id] = {
                "x": cursor_x,
                "y": current_y,
                "w": float(node["w"]),
                "h": float(node["h"]),
            }
            cursor_x += float(node["w"]) + X_GAP
        current_y += row_height + Y_GAP

    min_x = min(position["x"] for position in positions.values())
    x_shift = PAD - min_x
    for position in positions.values():
        position["x"] = round(position["x"] + x_shift, 2)
        position["y"] = round(position["y"], 2)
    for node_id, position in positions.items():
        by_id[node_id]["x"] = position["x"]
        by_id[node_id]["y"] = position["y"]
        by_id[node_id]["w"] = position["w"]
        by_id[node_id]["h"] = position["h"]

    max_x = max(position["x"] + position["w"] for position in positions.values())
    max_y = max(position["y"] + position["h"] for position in positions.values())
    min_node_x = min(position["x"] for position in positions.values())
    left_lane = max(12.0, min_node_x - LANE_GAP)
    right_lane = max_x + LANE_GAP

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        outgoing[str(edge.get("from") or "")].append(edge)
    left_count = 0
    right_count = 0
    edge_layout: dict[str, dict[str, Any]] = {}
    for edge in edges:
        source_id = str(edge.get("from") or "")
        target_id = str(edge.get("to") or "")
        source = positions.get(source_id)
        target = positions.get(target_id)
        if source is None or target is None:
            continue
        kind = str(edge.get("kind") or "next")
        sx, sy = _source_point(source, edge, outgoing.get(source_id, []))
        tx, ty = _target_point(target, edge)
        label = str(edge.get("label") or "")
        if kind in {"back", "continue"}:
            lane_x = left_lane - left_count * LANE_STEP
            left_count += 1
            points = [(sx, sy), (lane_x, sy), (lane_x, ty), (tx, ty)]
            label_xy = (lane_x + 4.0, max(sy, ty) - 6.0)
        elif kind in {"break", "loop_complete"}:
            lane_x = right_lane + right_count * LANE_STEP
            right_count += 1
            points = [(sx, sy), (lane_x, sy), (lane_x, ty - 8.0), (tx, ty - 8.0), (tx, ty)]
            label_xy = (lane_x + 4.0, max(sy, ty) - 6.0)
        else:
            mid_y = (sy + ty) / 2.0
            points = [(sx, sy), (sx, mid_y), (tx, mid_y), (tx, ty)]
            label_xy = ((sx + tx) / 2.0, mid_y - 6.0)
        edge_layout[str(edge.get("id"))] = {
            "d": _orth_path(points),
            "labelX": round(label_xy[0], 2),
            "labelY": round(label_xy[1], 2),
            "kind": kind,
            "text": label,
        }

    canvas_right = max(max_x, right_lane + max(0, right_count - 1) * LANE_STEP)
    return {
        "mode": "execution-flow",
        "canvas": {
            "width": round(canvas_right + PAD, 2),
            "height": round(max_y + PAD, 2),
            "padding": PAD,
        },
        "nodes": positions,
        "edges": edge_layout,
        "ranks": ranks,
        "flowId": flow_id,
    }
