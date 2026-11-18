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


def test_validator_rejects_removed_module_edges_and_main_module_fields() -> None:
    bundle = build_architecture(ROOT)
    bundle["moduleGraphs"][0]["edges"] = []
    bundle["projectGraph"]["mainModuleId"] = bundle["projectGraph"]["modules"][0]["id"]
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "MODULE_EDGES_REMOVED" for issue in issues)
    assert any(issue["code"] == "PROJECT_LEGACY_FIELD" for issue in issues)


def test_validator_detects_invalid_api_exposure_and_capability_kind() -> None:
    bundle = build_architecture(ROOT)
    bundle["functionDetails"][0]["apiExposure"] = "invalid"
    bundle["moduleGraphs"][0]["providedApis"][0]["kind"] = "invalid"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "DETAIL_EXPOSURE" for issue in issues)
    assert any(issue["code"] == "PROVIDED_API_KIND" for issue in issues)


def test_validator_detects_invalid_call_usage_kind() -> None:
    bundle = build_architecture(ROOT)
    bundle["callSites"][0]["usageKind"] = "invalid"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "CALL_USAGE_KIND" for issue in issues)


def test_validator_detects_noncanonical_execution_interface_capability() -> None:
    bundle = build_architecture(ROOT)
    flow = bundle["projectGraph"]["executionFlows"][0]
    interface = next(node for node in flow["nodes"] if node.get("kind") == "interface")
    interface["capabilityId"] = "api:missing"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "EXEC_INTERFACE_CAPABILITY" for issue in issues)
