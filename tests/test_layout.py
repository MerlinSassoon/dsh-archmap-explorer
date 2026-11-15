from __future__ import annotations

import re
from pathlib import Path

from archmap.pipeline import build_architecture

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def _rects_overlap(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"] + 0.5
        or b["x"] + b["w"] <= a["x"] + 0.5
        or a["y"] + a["h"] <= b["y"] + 0.5
        or b["y"] + b["h"] <= a["y"] + 0.5
    )


def test_layout_invariants() -> None:
    bundle = build_architecture(ROOT)
    for flow in bundle["functionFlows"]:
        layout = flow["layout"]
        nodes = list(layout["nodes"].items())
        for index, (_, a) in enumerate(nodes):
            for _, b in nodes[index + 1 :]:
                assert not _rects_overlap(a, b), flow["id"]
        for node in flow["nodes"]:
            if node["type"] == "merge":
                merge = layout["nodes"][node["id"]]
                branch = layout["nodes"][node["mergeOf"]]
                assert abs(merge["x"] + merge["w"] / 2 - branch["x"] - branch["w"] / 2) <= 0.5
        for edge in flow["edges"]:
            path = layout["edges"][edge["id"]]["d"]
            assert re.fullmatch(r"[MLQ0-9.\- ]+", path)
            current = None
            for command, numbers in re.findall(r"([MLQ])\s+([^MLQ]+)", path):
                values = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", numbers)]
                if command == "M":
                    current = values[:2]
                elif command == "L":
                    assert abs(current[0] - values[0]) < 0.01 or abs(current[1] - values[1]) < 0.01
                    current = values[:2]
                elif command == "Q":
                    current = values[2:4]
