from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterable


TOP = 40
ROW_H = 112
PAD = 48
ARM_GAP = 112
LANE_GAP = 28
LANE_STEP = 14
PORT_DX = 28
LOOP_PORT_DX = 32
MIN_ARM_EXTENT = 70
RADIUS = 8


class LayoutError(RuntimeError):
    pass


@dataclass
class LaneRegistry:
    lanes: dict[Any, list[list[tuple[float, float]]]] = field(default_factory=dict)

    def alloc(self, key: Any, y0: float, y1: float) -> int:
        lo, hi = min(y0, y1), max(y0, y1)
        spans_list = self.lanes.setdefault(key, [])
        for index, spans in enumerate(spans_list):
            if all(hi < a or lo > b for a, b in spans):
                spans.append((lo, hi))
                return index
        spans_list.append([(lo, hi)])
        return len(spans_list) - 1


def _node_map(flow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in flow["nodes"]}


def _block_map(flow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {block["id"]: block for block in flow["blocks"]}


def _is_descendant_block(blocks: dict[str, dict[str, Any]], block_id: str | None, ancestor_id: str) -> bool:
    current = block_id
    while current:
        if current == ancestor_id:
            return True
        block = blocks.get(current)
        current = block.get("parentId") if block else None
    return False


def _nodes_in_block(flow: dict[str, Any], block_id: str) -> list[dict[str, Any]]:
    blocks = _block_map(flow)
    nodes = _node_map(flow)
    result: list[dict[str, Any]] = []

    def walk(current_id: str) -> None:
        block = blocks.get(current_id)
        if not block:
            return
        if block["kind"] == "sequence":
            for item in block.get("items", []):
                if item in nodes:
                    result.append(nodes[item])
                elif item in blocks:
                    walk(item)
        elif block["kind"] == "if":
            owner = nodes.get(block.get("ownerId"))
            if owner:
                result.append(owner)
            if block.get("then"):
                walk(block["then"])
            if block.get("else"):
                walk(block["else"])
            merge = nodes.get(block.get("merge"))
            if merge:
                result.append(merge)
        elif block["kind"] == "loop":
            owner = nodes.get(block.get("ownerId"))
            if owner:
                result.append(owner)
            if block.get("body"):
                walk(block["body"])

    walk(block_id)
    return result


def _children_blocks(flow: dict[str, Any]) -> dict[str | None, list[str]]:
    result: dict[str | None, list[str]] = defaultdict(list)
    for block in flow["blocks"]:
        result[block.get("parentId")].append(block["id"])
    return result


def _loop_ancestor(blocks: dict[str, dict[str, Any]], block_id: str | None) -> str | None:
    current = block_id
    while current:
        block = blocks.get(current)
        if not block:
            return None
        if block["kind"] == "loop":
            return block["ownerId"]
        current = block.get("parentId")
    return None


def _enclosing_loop_headers(blocks: dict[str, dict[str, Any]], block_id: str | None) -> set[str]:
    """Return loop header ids whose body contains the given block, including self."""
    result: set[str] = set()
    current = block_id
    while current:
        block = blocks.get(current)
        if not block:
            break
        if block["kind"] == "loop" and block.get("ownerId"):
            result.add(block["ownerId"])
        current = block.get("parentId")
    return result


def _compute_ranks(flow: dict[str, Any]) -> dict[str, int]:
    nodes = _node_map(flow)
    blocks = _block_map(flow)
    entry_id = flow["entryNodeId"]
    exit_id = flow["exitNodeId"]
    loop_headers = {node["id"] for node in flow["nodes"] if node["type"] == "loop"}

    dag: list[tuple[str, str]] = []
    next_targets: dict[str, str] = {}
    for edge in flow["edges"]:
        if edge["type"] != "next_step":
            continue
        src, dst = edge["from"], edge["to"]
        if src not in nodes or dst not in nodes:
            continue
        flow_kind = edge.get("flow")
        if flow_kind == "loop_exit":
            next_targets[src] = dst
        if flow_kind in {"back", "continue"}:
            continue
        # Any edge entering a loop header from its body is a back edge for layering.
        if dst in loop_headers and src != dst and flow_kind != "loop_body":
            src_block = nodes[src].get("blockId")
            loop_block = None
            for block in flow["blocks"]:
                if block["kind"] == "loop" and block.get("ownerId") == dst:
                    loop_block = block
                    break
            if loop_block and _is_descendant_block(blocks, src_block, loop_block.get("body", "")):
                continue
        dag.append((src, dst))

    # Phantom edges make loop bodies sit above the loop's after target.
    for block in flow["blocks"]:
        if block["kind"] != "loop":
            continue
        loop_id = block.get("ownerId")
        after = next_targets.get(loop_id, exit_id)
        enclosing_loops = _enclosing_loop_headers(blocks, block["id"])
        # If the loop's after target is its own or an enclosing loop header,
        # that is a back edge. Adding phantom edges to it would create a rank cycle.
        if after in enclosing_loops:
            continue
        body_nodes = _nodes_in_block(flow, block.get("body", "")) if block.get("body") else []
        for body_node in body_nodes:
            if body_node["id"] != after:
                dag.append((body_node["id"], after))

    # Guard/no-merge if: subsequent join must sit after the longest arm.
    for block in flow["blocks"]:
        if block["kind"] != "if" or block.get("merge"):
            continue
        join = _next_join_for_block(flow, block["id"], exit_id)
        if not join:
            continue
        # A join that is the if's own/enclosing loop header is a back edge.
        # A sibling loop header is a real forward join and still needs a phantom
        # constraint so a terminating arm cannot share its rank.
        if join in _enclosing_loop_headers(blocks, block["id"]):
            continue
        for arm_key in ("then", "else"):
            arm_id = block.get(arm_key)
            if not arm_id:
                continue
            for arm_node in _nodes_in_block(flow, arm_id):
                if arm_node["id"] != join:
                    dag.append((arm_node["id"], join))

    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {node_id: 0 for node_id in nodes}
    for src, dst in sorted(set(dag)):
        if src == dst or dst not in nodes or src not in nodes:
            continue
        adjacency[src].append(dst)
        indegree[dst] += 1

    queue = deque([entry_id])
    rank: dict[str, int] = {entry_id: 0}
    visited: list[str] = []
    while queue:
        current = queue.popleft()
        visited.append(current)
        for nxt in sorted(set(adjacency.get(current, []))):
            rank[nxt] = max(rank.get(nxt, 0), rank.get(current, 0) + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(visited) != len(nodes):
        # Keep the renderer usable for unusual dynamic-control fixtures. Assign a stable
        # rank to any remaining node after its known predecessors.
        missing = [node_id for node_id in nodes if node_id not in visited]
        flow.setdefault("diagnostics", []).append(
            {
                "severity": "warning",
                "code": "CFG_CYCLE",
                "message": "执行流仍包含未消解环，已使用稳定回退 rank",
                "functionId": flow["id"],
            }
        )
        # Nodes can have a tentative rank from a processed predecessor while
        # still being unvisited. Reassign every unvisited node to a unique tail
        # rank; keeping tentative values would put them on occupied rows.
        next_rank = max((rank[node_id] for node_id in visited), default=0) + 1
        for node_id in sorted(missing):
            rank[node_id] = next_rank
            next_rank += 1
    max_rank = max((value for node_id, value in rank.items() if node_id != exit_id), default=0)
    rank[exit_id] = max_rank + 1
    return rank


def _next_join_for_block(flow: dict[str, Any], block_id: str, fallback: str) -> str | None:
    blocks = _block_map(flow)
    nodes = _node_map(flow)
    current = block_id
    while current:
        block = blocks.get(current)
        if not block:
            return fallback
        parent_id = block.get("parentId")
        parent = blocks.get(parent_id)
        if parent and parent["kind"] == "sequence":
            items = parent.get("items", [])
            if current in items:
                index = items.index(current)
                if index + 1 < len(items):
                    nxt = items[index + 1]
                    if nxt in nodes:
                        return nxt
                    next_block = blocks.get(nxt)
                    if next_block:
                        return next_block.get("ownerId")
        # If an if is the last item in a loop body, its join is the loop back target.
        if parent and parent["kind"] == "loop":
            return parent.get("ownerId")
        current = parent_id
    return fallback


def _measure_node(node: dict[str, Any]) -> tuple[float, float]:
    return float(node.get("w", 240)), float(node.get("h", 56))


def _extent(flow: dict[str, Any], block_id: str) -> tuple[float, float]:
    blocks = _block_map(flow)
    nodes = _node_map(flow)
    block = blocks[block_id]
    kind = block["kind"]
    if kind == "sequence":
        left = right = 0.0
        for item in block.get("items", []):
            if item in nodes:
                w, _ = _measure_node(nodes[item])
                left = max(left, w / 2)
                right = max(right, w / 2)
            elif item in blocks:
                child_left, child_right = _extent(flow, item)
                left = max(left, child_left)
                right = max(right, child_right)
        return left, right
    if kind == "if":
        owner = nodes[block["ownerId"]]
        ow, _ = _measure_node(owner)
        then_l, then_r = _extent(flow, block["then"]) if block.get("then") else (MIN_ARM_EXTENT, MIN_ARM_EXTENT)
        else_l, else_r = _extent(flow, block["else"]) if block.get("else") else (MIN_ARM_EXTENT, MIN_ARM_EXTENT)
        left = max(ow / 2, ARM_GAP / 2 + then_l + then_r)
        right = max(ow / 2, ARM_GAP / 2 + else_l + else_r)
        return left, right
    if kind == "loop":
        owner = nodes[block["ownerId"]]
        ow, _ = _measure_node(owner)
        body_l, body_r = _extent(flow, block["body"]) if block.get("body") else (0.0, 0.0)
        flow_counts = {"left": 0, "right": 0}
        for edge in flow["edges"]:
            if edge["type"] != "next_step":
                continue
            if edge.get("flow") in {"back", "continue"}:
                flow_counts["left"] += 1
            elif edge.get("flow") in {"loop_exit", "break"}:
                flow_counts["right"] += 1
        left_need = LANE_GAP + LANE_STEP * max(0, flow_counts["left"] - 1)
        right_need = LANE_GAP + LANE_STEP * max(0, flow_counts["right"] - 1)
        return max(ow / 2, body_l + left_need), max(ow / 2, body_r + right_need)
    return 0.0, 0.0


def _place(flow: dict[str, Any], block_id: str, cx: float) -> None:
    blocks = _block_map(flow)
    nodes = _node_map(flow)
    block = blocks[block_id]
    kind = block["kind"]
    if kind == "sequence":
        for item in block.get("items", []):
            if item in nodes:
                nodes[item]["cx"] = cx
            elif item in blocks:
                _place(flow, item, cx)
        return
    if kind == "if":
        branch = nodes[block["ownerId"]]
        branch["cx"] = cx
        if block.get("then"):
            tl, tr = _extent(flow, block["then"])
            then_cx = cx - (ARM_GAP / 2 + tr)
            _place(flow, block["then"], then_cx)
        if block.get("else"):
            el, er = _extent(flow, block["else"])
            else_cx = cx + (ARM_GAP / 2 + el)
            _place(flow, block["else"], else_cx)
        if block.get("merge"):
            nodes[block["merge"]]["cx"] = cx
        return
    if kind == "loop":
        nodes[block["ownerId"]]["cx"] = cx
        if block.get("body"):
            _place(flow, block["body"], cx)


def _layout_columns(flow: dict[str, Any], rank: dict[str, int]) -> None:
    nodes = _node_map(flow)
    root = flow["rootBlockId"]
    _extent(flow, root)
    _place(flow, root, 0.0)
    nodes[flow["entryNodeId"]]["cx"] = 0.0
    nodes[flow["exitNodeId"]]["cx"] = 0.0
    for node in flow["nodes"]:
        if "cx" not in node:
            node["cx"] = 0.0
        node["rank"] = rank[node["id"]]
        _, h = _measure_node(node)
        node["y"] = TOP + rank[node["id"]] * ROW_H + (ROW_H - h) / 2
        node["x"] = node["cx"] - node["w"] / 2
    min_x = min(node["x"] for node in flow["nodes"])
    dx = PAD - min_x
    for node in flow["nodes"]:
        node["x"] += dx
        node["cx"] += dx


def _node_rect(node: dict[str, Any]) -> dict[str, float]:
    return {"x": node["x"], "y": node["y"], "w": node["w"], "h": node["h"]}


def _top_center(node: dict[str, Any]) -> tuple[float, float]:
    return node["cx"], node["y"]


def _bottom_center(node: dict[str, Any]) -> tuple[float, float]:
    return node["cx"], node["y"] + node["h"]


def _left_mid(node: dict[str, Any]) -> tuple[float, float]:
    return node["x"], node["y"] + node["h"] / 2


def _right_mid(node: dict[str, Any]) -> tuple[float, float]:
    return node["x"] + node["w"], node["y"] + node["h"] / 2


def _degenerate(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in points:
        if not result or abs(point[0] - result[-1][0]) > 0.01 or abs(point[1] - result[-1][1]) > 0.01:
            result.append((round(point[0], 2), round(point[1], 2)))
    changed = True
    while changed and len(result) > 2:
        changed = False
        compact: list[tuple[float, float]] = [result[0]]
        for index in range(1, len(result) - 1):
            a, b, c = result[index - 1], result[index], result[index + 1]
            if (abs(a[0] - b[0]) < 0.01 and abs(b[0] - c[0]) < 0.01) or (
                abs(a[1] - b[1]) < 0.01 and abs(b[1] - c[1]) < 0.01
            ):
                changed = True
                continue
            compact.append(b)
        compact.append(result[-1])
        result = compact
    return result


def rounded_path(points: list[tuple[float, float]], radius: float = RADIUS) -> str:
    pts = _degenerate(points)
    if len(pts) < 2:
        return ""
    if len(pts) == 2:
        return f"M {pts[0][0]} {pts[0][1]} L {pts[1][0]} {pts[1][1]}"
    parts = [f"M {pts[0][0]} {pts[0][1]}"]
    for index in range(1, len(pts) - 1):
        prev, current, nxt = pts[index - 1], pts[index], pts[index + 1]
        v1 = (prev[0] - current[0], prev[1] - current[1])
        v2 = (nxt[0] - current[0], nxt[1] - current[1])
        len1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
        len2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
        if len1 < 0.01 or len2 < 0.01:
            continue
        rr = min(radius, len1 / 2, len2 / 2)
        p1 = (current[0] + v1[0] / len1 * rr, current[1] + v1[1] / len1 * rr)
        p2 = (current[0] + v2[0] / len2 * rr, current[1] + v2[1] / len2 * rr)
        parts.append(f"L {round(p1[0], 2)} {round(p1[1], 2)}")
        parts.append(f"Q {current[0]} {current[1]} {round(p2[0], 2)} {round(p2[1], 2)}")
    parts.append(f"L {pts[-1][0]} {pts[-1][1]}")
    return " ".join(parts)


def _route_next(src: dict[str, Any], dst: dict[str, Any]) -> list[tuple[float, float]]:
    sx, sy = _bottom_center(src)
    tx, ty = _top_center(dst)
    if abs(sx - tx) < 0.5:
        return [(sx, sy), (tx, ty)]
    mid = (sy + ty) / 2
    return [(sx, sy), (sx, mid), (tx, mid), (tx, ty)]


def _route_control(
    flow: dict[str, Any],
    edge: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    lanes: LaneRegistry,
    nodes_min_x: float,
    nodes_max_x: float,
    canvas_cx: float,
) -> list[tuple[float, float]]:
    src = nodes[edge["from"]]
    dst = nodes[edge["to"]]
    kind = edge.get("flow")
    if kind == "next":
        return _route_next(src, dst)
    if kind in {"true", "false"}:
        sx = src["cx"] - PORT_DX if kind == "true" else src["cx"] + PORT_DX
        sy = src["y"] + src["h"]
        tx, ty = _top_center(dst)
        y = sy + 24
        return [(sx, sy), (sx, y), (tx, y), (tx, ty)]
    if kind == "loop_body":
        sx = src["cx"] - LOOP_PORT_DX
        sy = src["y"] + src["h"]
        tx, ty = _top_center(dst)
        y = sy + 20
        return [(sx, sy), (sx, y), (tx, y), (tx, ty)]
    if kind == "merge":
        sx, sy = _bottom_center(src)
        px = dst["cx"] - PORT_DX if src["cx"] < dst["cx"] else dst["cx"] + PORT_DX
        y = dst["y"] - 20
        return [(sx, sy), (sx, y), (px, y), (px, dst["y"])]
    if kind in {"back", "continue"}:
        loop = nodes.get(dst["id"])
        if loop is None or loop.get("type") != "loop":
            return _route_next(src, dst)
        sx, sy = _bottom_center(src)
        lane_key = ("left", dst["id"])
        lane_index = lanes.alloc(lane_key, sy + 20, loop["y"] + loop["h"] / 2)
        # Use the measured extent as the local lane anchor.
        body_min = min(n["x"] for n in flow["nodes"])
        for block in flow["blocks"]:
            if block["kind"] == "loop" and block.get("ownerId") == dst["id"] and block.get("body"):
                body_nodes = _nodes_in_block(flow, block["body"])
                if body_nodes:
                    body_min = min(n["x"] for n in body_nodes)
                break
        lane_x = body_min - LANE_GAP - lane_index * LANE_STEP
        y = sy + 20
        return [(sx, sy), (sx, y), (lane_x, y), (lane_x, loop["y"] + loop["h"] / 2), (loop["x"], loop["y"] + loop["h"] / 2)]
    if kind in {"loop_exit", "break"}:
        loop = nodes.get(src["id"]) if src.get("type") == "loop" else None
        if loop is None:
            # A break node: locate the nearest loop from its block ancestry.
            loop = _nearest_loop_for_node(flow, src, nodes)
        if loop is None:
            return _route_next(src, dst)
        lane_key = ("right", loop["id"])
        if kind == "loop_exit":
            src_point = _right_mid(loop)
            y0 = src_point[1]
        else:
            src_point = _bottom_center(src)
            y0 = src_point[1] + 20
        lane_index = lanes.alloc(lane_key, y0, dst["y"] - 20)
        body_max = max(n["x"] + n["w"] for n in flow["nodes"])
        for block in flow["blocks"]:
            if block["kind"] == "loop" and block.get("ownerId") == loop["id"] and block.get("body"):
                body_nodes = _nodes_in_block(flow, block["body"])
                if body_nodes:
                    body_max = max(n["x"] + n["w"] for n in body_nodes)
                break
        lane_x = body_max + LANE_GAP + lane_index * LANE_STEP
        y = dst["y"] - 20
        if kind == "loop_exit":
            return [src_point, (lane_x, src_point[1]), (lane_x, y), (dst["cx"], y), (dst["cx"], dst["y"])]
        return [
            src_point,
            (src_point[0], y0),
            (lane_x, y0),
            (lane_x, y),
            (dst["cx"], y),
            (dst["cx"], dst["y"]),
        ]
    if kind in {"return", "exception"}:
        sx, sy = _bottom_center(src)
        tx, ty = _top_center(dst)
        if abs(sx - tx) < 0.5 and sy < ty:
            return [(sx, sy), (tx, ty)]
        side = "left" if sx < tx else "right"
        lane_key = ("global", side)
        lane_index = lanes.alloc(lane_key, sy + 20, ty - 16)
        lane_x = (
            nodes_min_x - LANE_GAP - lane_index * LANE_STEP
            if side == "left"
            else nodes_max_x + LANE_GAP + lane_index * LANE_STEP
        )
        bus_y = ty - 16
        return [(sx, sy), (sx, sy + 20), (lane_x, sy + 20), (lane_x, bus_y), (tx, bus_y), (tx, ty)]
    return _route_next(src, dst)


def _nearest_loop_for_node(
    flow: dict[str, Any], node: dict[str, Any], nodes: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    blocks = _block_map(flow)
    current = node.get("blockId")
    while current:
        block = blocks.get(current)
        if not block:
            return None
        if block["kind"] == "loop":
            return nodes.get(block.get("ownerId"))
        current = block.get("parentId")
    return None


def _route_data(
    src: dict[str, Any],
    dst: dict[str, Any],
    lanes: LaneRegistry,
    nodes_min_x: float,
    nodes_max_x: float,
    canvas_cx: float,
) -> list[tuple[float, float]]:
    sx, sy = _bottom_center(src)
    tx, ty = _top_center(dst)
    side = "left" if (src["cx"] + dst["cx"]) / 2 < canvas_cx else "right"
    y0 = sy + 12
    y1 = max(ty - 12, y0 + 8)
    lane_index = lanes.alloc(("data", side), y0, y1)
    lane_x = (
        nodes_min_x - LANE_GAP - 6 - lane_index * LANE_STEP
        if side == "left"
        else nodes_max_x + LANE_GAP + 6 + lane_index * LANE_STEP
    )
    return [(sx, sy), (sx, y0), (lane_x, y0), (lane_x, y1), (tx, y1), (tx, ty)]


def _route_edges(flow: dict[str, Any]) -> None:
    nodes = _node_map(flow)
    nodes_min_x = min(node["x"] for node in flow["nodes"])
    nodes_max_x = max(node["x"] + node["w"] for node in flow["nodes"])
    canvas_cx = (nodes_min_x + nodes_max_x) / 2
    lanes = LaneRegistry()
    for edge in flow["edges"]:
        if edge["type"] != "next_step":
            continue
        points = _route_control(flow, edge, nodes, lanes, nodes_min_x, nodes_max_x, canvas_cx)
        edge["points"] = [[round(x, 2), round(y, 2)] for x, y in points]
        edge["d"] = rounded_path(points)
        if edge.get("flow") in {"true", "false"}:
            label_x, label_y = points[0][0] + 8, points[0][1] + 10
            edge["labelPos"] = {"x": round(label_x, 2), "y": round(label_y, 2)}
        elif edge.get("flow") == "back":
            edge["labelPos"] = {"x": round(points[-2][0] - 8, 2), "y": round((points[1][1] + points[3][1]) / 2, 2)}
    for edge in flow["edges"]:
        if edge["type"] != "data_dep":
            continue
        src = nodes.get(edge["from"])
        dst = nodes.get(edge["to"])
        if not src or not dst:
            continue
        points = _route_data(src, dst, lanes, nodes_min_x, nodes_max_x, canvas_cx)
        edge["points"] = [[round(x, 2), round(y, 2)] for x, y in points]
        edge["d"] = rounded_path(points)
        edge["labelPos"] = {
            "x": round(points[2][0] + 5, 2),
            "y": round((points[2][1] + points[3][1]) / 2, 2),
        }


def _build_layout(flow: dict[str, Any]) -> dict[str, Any]:
    rank = _compute_ranks(flow)
    _layout_columns(flow, rank)
    _route_edges(flow)
    min_x = min(node["x"] for node in flow["nodes"])
    min_y = min(node["y"] for node in flow["nodes"])
    max_x = max(node["x"] + node["w"] for node in flow["nodes"])
    max_y = max(node["y"] + node["h"] for node in flow["nodes"])
    for edge in flow["edges"]:
        for point in edge.get("points", []):
            min_x = min(min_x, point[0])
            min_y = min(min_y, point[1])
            max_x = max(max_x, point[0])
            max_y = max(max_y, point[1])
    dx = PAD - min(min_x, PAD)
    dy = PAD - min(min_y, PAD)
    if dx or dy:
        for node in flow["nodes"]:
            node["x"] = round(node["x"] + dx, 2)
            node["y"] = round(node["y"] + dy, 2)
            node["cx"] = round(node["cx"] + dx, 2)
        for edge in flow["edges"]:
            edge["points"] = [[round(x + dx, 2), round(y + dy, 2)] for x, y in edge.get("points", [])]
            edge["d"] = rounded_path([(x, y) for x, y in edge.get("points", [])])
            if "labelPos" in edge:
                edge["labelPos"]["x"] = round(edge["labelPos"]["x"] + dx, 2)
                edge["labelPos"]["y"] = round(edge["labelPos"]["y"] + dy, 2)
    layout_nodes = {
        node["id"]: {
            "x": round(node["x"], 2),
            "y": round(node["y"], 2),
            "w": node["w"],
            "h": node["h"],
            "cx": round(node["cx"], 2),
            "rank": node["rank"],
        }
        for node in flow["nodes"]
    }
    layout_edges = {}
    for edge in flow["edges"]:
        item: dict[str, Any] = {
            "d": edge["d"],
            "points": edge.get("points", []),
        }
        if "labelPos" in edge:
            item["label"] = {
                "x": edge["labelPos"]["x"],
                "y": edge["labelPos"]["y"],
                "text": edge.get("label") or edge.get("variable") or "",
            }
        layout_edges[edge["id"]] = item
    return {
        "canvas": {
            "width": round(max_x + PAD + dx, 2),
            "height": round(max_y + PAD + dy, 2),
            "padding": PAD,
        },
        "nodes": layout_nodes,
        "edges": layout_edges,
    }


def layout_function_flow(flow: dict[str, Any]) -> dict[str, Any]:
    flow["layout"] = _build_layout(flow)
    for node in flow["nodes"]:
        node.pop("cx", None)
        node.pop("rank", None)
    return flow


def layout_function_flows(flows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [layout_function_flow(flow) for flow in flows]
