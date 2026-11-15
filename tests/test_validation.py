from __future__ import annotations

from pathlib import Path

from archmap.pipeline import build_architecture
from archmap.validate import validate_bundle

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def test_validator_detects_broken_edge() -> None:
    bundle = build_architecture(ROOT)
    bundle["functionFlows"][0]["edges"].append(
        {"id": "e:bad", "from": "missing", "to": bundle["functionFlows"][0]["exitNodeId"], "type": "next_step", "flow": "next"}
    )
    issues = validate_bundle(bundle)
    assert any(issue["code"] in {"EDGE_ENDPOINT", "NO_EXIT_PATH", "NODE_OVERLAP"} for issue in issues)
