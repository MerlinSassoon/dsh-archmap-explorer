from __future__ import annotations

from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def test_validator_detects_broken_call_target() -> None:
    bundle = build_architecture(ROOT)
    bundle["callSites"][0]["resolved"] = True
    bundle["callSites"][0]["toFunctionId"] = "fn:missing"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "CALL_TO_MISSING" for issue in issues)


def test_validator_detects_broken_module_edge() -> None:
    bundle = build_architecture(ROOT)
    bundle["moduleGraphs"][0]["edges"].append(
        {"id": "e:bad", "from": "missing", "to": bundle["moduleGraphs"][0]["nodes"][0]["id"], "primaryType": "call", "relations": ["call"], "role": "internal", "confidence": "low", "evidence": []}
    )
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "MODULE_EDGE_ENDPOINT" for issue in issues)


def test_validator_detects_invalid_api_exposure_and_capability_kind() -> None:
    bundle = build_architecture(ROOT)
    bundle["functionDetails"][0]["apiExposure"] = "invalid"
    bundle["moduleGraphs"][0]["providedApis"][0]["kind"] = "invalid"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "DETAIL_EXPOSURE" for issue in issues)
    assert any(issue["code"] == "PROVIDED_API_KIND" for issue in issues)
