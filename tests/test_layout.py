from __future__ import annotations

from pathlib import Path

from archmap.pipeline import build_architecture

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
        for edge in graph["edges"]:
            # The project page is a capability-card board; it intentionally
            # omits dependency paths from the default projection layout.  Any
            # edge whose endpoints are laid out must still have a valid path.
            if edge["from"] not in layout["nodes"] or edge["to"] not in layout["nodes"]:
                continue
            path = layout["edges"][edge["id"]]["d"]
            assert path.startswith("M ")
