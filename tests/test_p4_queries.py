from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager
from archmap.utility.query_utility import build_dsm, build_impact, build_trace

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "p4_demo"
REPO_ROOT = Path(__file__).parent.parent


def _bundle() -> dict:
    return build_architecture(ROOT)


def _class_id(name: str) -> str:
    return f"cls:app.{name}"


def test_structural_relations_cover_uses_aggregation_composition_and_instantiation() -> None:
    bundle = _bundle()
    relations = {
        (relation["fromClassId"], relation["kind"], relation["toClassId"]): relation
        for relation in bundle["projectGraph"]["typeRelations"]
    }
    manager = _class_id("manager.OrderManager")
    assert (manager, "uses", _class_id("model.Order")) in relations
    assert (manager, "aggregates", _class_id("model.Config")) in relations
    assert (manager, "aggregates", _class_id("repository.Repository")) in relations
    assert (manager, "composes", _class_id("cache.Cache")) in relations
    assert (manager, "instantiates", _class_id("cache.Cache")) in relations
    for relation in relations.values():
        assert relation["source"]
        assert relation["fromProviderRole"] == "manager"
        assert relation["toProviderRole"] in {"config", "model", "manager"}
        assert relation["evidenceFunctionIds"]
    assert bundle["stats"]["structuralRelations"] >= 5


def test_user_surfaces_are_entrypoint_reachable_and_source_backed() -> None:
    bundle = _bundle()
    surfaces = bundle["projectGraph"]["userSurfaces"]
    kinds = {surface["kind"] for surface in surfaces}
    assert {"cli_input", "cli_output"}.issubset(kinds)
    input_surface = next(surface for surface in surfaces if surface["kind"] == "cli_input")
    assert input_surface["entrypointIds"] == ["fn:app.main.main"]
    assert input_surface["evidenceFunctionIds"] == ["fn:app.main.run_cli"]
    assert input_surface["confidence"] == "high"
    run_cli = next(item for item in bundle["functionDetails"] if item["name"] == "run_cli")
    assert run_cli["userSurfaceKinds"] == ["cli_input", "cli_output"]

    page = next(surface for surface in surfaces if surface["kind"] == "cli_output")
    assert page["moduleId"] == "main"
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_trace_crosses_internal_helpers_and_polymorphic_edges() -> None:
    bundle = _bundle()
    trace = build_trace(bundle, "fn:app.main.main", max_depth=5)
    node_ids = {item["nodeId"] for item in trace["nodes"]}
    assert "fn:app.main.run_cli" in node_ids
    assert "fn:app.manager.OrderManager.place" in node_ids
    assert "fn:app.repository.Repository.save" in node_ids
    assert "fn:app.cache.Cache.put" in node_ids
    assert trace["paths"]
    assert not trace["truncated"]


def test_impact_propagates_from_api_implementation_to_callers() -> None:
    before = _bundle()
    after = copy.deepcopy(before)
    save = next(item for item in after["functionDetails"] if item["id"] == "fn:app.repository.Repository.save")
    save["signature"] = "def save(self, order, strict: bool = False) -> bool"
    save["sourceHash"] = "sha256:" + "1" * 64
    result = build_impact(before, after)
    impacted = {item["nodeId"] for item in result["impacts"]}
    assert "fn:app.repository.Repository.save" in impacted
    assert "fn:app.manager.OrderManager.place" in impacted
    assert "fn:app.main.run_cli" in impacted
    assert result["summary"]["total"] >= 3


def test_dsm_reports_module_and_provider_relation_weights() -> None:
    bundle = _bundle()
    module_dsm = build_dsm(bundle, level="module")
    assert module_dsm["matrix"]["service"]["domain"]["count"] >= 5
    assert "composes" in module_dsm["matrix"]["service"]["domain"]["kinds"]
    provider_dsm = build_dsm(bundle, level="provider")
    manager = _class_id("manager.OrderManager")
    assert manager in provider_dsm["matrix"]
    assert provider_dsm["matrix"][manager][_class_id("cache.Cache")]["kinds"]["composes"] == 1


def test_p4_cli_commands_read_the_bundle(tmp_path: Path) -> None:
    out = tmp_path / "out"
    build = subprocess.run(
        [sys.executable, "-m", "archmap", "build", str(ROOT), "--out", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    bundle = out / "architecture.json"
    for command in (
        [sys.executable, "-m", "archmap", "surfaces", str(bundle), "--json"],
        [sys.executable, "-m", "archmap", "trace", str(bundle), "--from", "fn:app.main.main", "--max-depth", "3", "--json"],
        [sys.executable, "-m", "archmap", "dsm", str(bundle), "--level", "module", "--json"],
    ):
        result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)

    bundle_data = json.loads(bundle.read_text(encoding="utf-8"))
    save = next(item for item in bundle_data["functionDetails"] if item["id"] == "fn:app.repository.Repository.save")
    save["signature"] = "def save(self, order, strict: bool = False) -> bool"
    save["sourceHash"] = "sha256:" + "2" * 64
    after = tmp_path / "after.json"
    after.write_text(json.dumps(bundle_data), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "archmap", "impact", str(bundle), str(after), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    impact = json.loads(result.stdout)
    assert impact["summary"]["total"] >= 3


def test_validator_rejects_bad_surface_and_structural_relation() -> None:
    bundle = _bundle()
    bundle["projectGraph"]["userSurfaces"][0]["kind"] = "invalid_surface"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "USER_SURFACE_KIND" for issue in issues)

    bundle = _bundle()
    bundle["projectGraph"]["typeRelations"][0]["toClassId"] = "cls:app.missing.Type"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "TYPE_RELATION_ENDPOINT" for issue in issues)


def test_p4_bundle_matches_schema() -> None:
    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    bundle = _bundle()
    schema = json.loads(
        (REPO_ROOT / "docs" / "schema" / "archmap-v6.4-bundle.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(bundle, schema)


def test_trace_exposes_low_confidence_unresolved_inbound_references() -> None:
    bundle = _bundle()
    bundle["callSites"].append(
        {
            "id": "call:test:unresolved-save",
            "fromFunctionId": "fn:app.main.main",
            "toFunctionId": None,
            "file": "app/main.py",
            "line": 99,
            "column": 1,
            "calleeText": "repository.save",
            "callText": "repository.save(order)",
            "resolved": False,
            "external": False,
            "polymorphic": False,
            "candidates": [],
            "confidence": "low",
            "dispatchKind": "static",
            "usageKind": "call",
        }
    )

    trace = build_trace(
        bundle,
        "fn:app.repository.Repository.save",
        direction="inbound",
    )

    assert trace["unresolvedCount"] == 1
    reference = trace["unresolvedReferences"][0]
    assert reference["callSiteId"] == "call:test:unresolved-save"
    assert reference["reason"] == "callee-name-match"
    assert reference["confidence"] == "low"
