from __future__ import annotations

from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager

build_architecture = PipelineManager().build_architecture

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def _overlap(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["w"] <= b["x"] + 0.5
        or b["x"] + b["w"] <= a["x"] + 0.5
        or a["y"] + a["h"] <= b["y"] + 0.5
        or b["y"] + b["h"] <= a["y"] + 0.5
    )


def test_macro_layout_has_valid_geometry() -> None:
    bundle = build_architecture(ROOT)
    graphs = [bundle["projectGraph"], *bundle["moduleGraphs"]]
    for graph in graphs:
        layout = graph["layout"]
        rects = list(layout["nodes"].values())
        assert rects
        for index, first in enumerate(rects):
            for second in rects[index + 1:]:
                assert not _overlap(first, second)
        if layout.get("mode") == "module-cards":
            assert layout["edges"] == {}
            continue
        for edge in graph.get("edges", []):
            if edge["from"] not in layout["nodes"] or edge["to"] not in layout["nodes"]:
                continue
            path = layout["edges"][edge["id"]]["d"]
            assert path.startswith("M ")
