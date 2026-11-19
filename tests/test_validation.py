from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager
from archmap.utility.config_utility import load_config

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


def test_config_unknown_keys_and_invalid_values_are_diagnosed(tmp_path: Path) -> None:
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(
        json.dumps(
            {
                "projectName": "bad-config",
                "unknownTopLevel": True,
                "modules": [
                    {
                        "id": "app",
                        "include": ["**/*.py"],
                        "role": "not-a-role",
                        "unknownModuleKey": 1,
                    }
                ],
                "contract": {
                    "unknownContractKey": 1,
                    "providerRoles": {"missing": "not-a-role"},
                    "apiExposure": {"fn:missing": "invalid"},
                },
            }
        ),
        encoding="utf-8",
    )
    config = load_config(tmp_path, config_path)
    codes = [item["code"] for item in config.config_diagnostics]
    assert "CONFIG_UNKNOWN_KEY" in codes
    assert "MODULE_ROLE_INVALID" in codes
    assert "PROVIDER_ROLE_INVALID" in codes
    assert "API_EXPOSURE_INVALID" in codes


def test_api_exposure_accepts_fn_prefix_and_rejects_unmatched_targets(tmp_path: Path) -> None:
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text(
        json.dumps(
            {
                "include": ["**/*.py"],
                "entrypoints": ["app.main:main"],
                "contract": {"apiExposure": {"fn:app.main.main": "internal"}},
            }
        ),
        encoding="utf-8",
    )
    accepted = build_architecture(ROOT, accepted_path)
    detail = next(
        item for item in accepted["functionDetails"] if item["id"] == "fn:app.main.main"
    )
    assert detail["apiExposure"] == "internal"
    assert detail["apiExposureSource"] == "config"

    rejected_path = tmp_path / "rejected.json"
    rejected_path.write_text(
        json.dumps(
            {
                "include": ["**/*.py"],
                "contract": {"apiExposure": {"fn:app.missing.main": "internal"}},
            }
        ),
        encoding="utf-8",
    )
    rejected = build_architecture(ROOT, rejected_path)
    assert any(
        item["code"] == "API_EXPOSURE_TARGET_UNRESOLVED"
        and item["severity"] == "error"
        for item in rejected["diagnostics"]
    )
