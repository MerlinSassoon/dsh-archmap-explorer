from __future__ import annotations

from pathlib import Path

from archmap.pipeline import build_architecture
from archmap.validate import validate_bundle

ROOT = Path(__file__).parent / "fixtures" / "control_flow_edges"
REPO_ROOT = Path(__file__).parent.parent


def _overlap(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"] + 0.5
        or b["x"] + b["w"] <= a["x"] + 0.5
        or a["y"] + a["h"] <= b["y"] + 0.5
        or b["y"] + b["h"] <= a["y"] + 0.5
    )


def _assert_no_overlap(flow: dict) -> None:
    nodes = list(flow["layout"]["nodes"].items())
    for index, (_, a) in enumerate(nodes):
        for _, b in nodes[index + 1 :]:
            assert not _overlap(a, b), flow["id"]


def test_guard_then_loop_rank_is_after_terminating_arm() -> None:
    bundle = build_architecture(ROOT)
    flow = next(item for item in bundle["functionFlows"] if item["name"] == "guard_then_loop")
    _assert_no_overlap(flow)
    return_node = next(node for node in flow["nodes"] if node.get("stepType") == "return")
    loop_node = next(node for node in flow["nodes"] if node["type"] == "loop")
    assert flow["layout"]["nodes"][return_node["id"]]["rank"] < flow["layout"]["nodes"][loop_node["id"]]["rank"]
    assert not [item for item in bundle["diagnostics"] if item.get("code") == "CFG_CYCLE"]


def test_nested_loop_last_has_no_rank_cycle() -> None:
    bundle = build_architecture(ROOT)
    flow = next(item for item in bundle["functionFlows"] if item["name"] == "nested_loop_last")
    _assert_no_overlap(flow)
    assert not [item for item in bundle["diagnostics"] if item.get("code") == "CFG_CYCLE"]


def test_self_build_validates_after_rank_fixes() -> None:
    bundle = build_architecture(REPO_ROOT / "archmap")
    issues = validate_bundle(bundle)
    assert not [issue for issue in issues if issue["severity"] == "error"]
    assert not [item for item in bundle["diagnostics"] if item.get("code") == "CFG_CYCLE"]
