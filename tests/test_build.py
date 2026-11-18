from __future__ import annotations

from pathlib import Path

from archmap.managers.graph_manager import GraphManager
from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate
semantic_fingerprint = GraphManager().semantic_fingerprint

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def test_build_bundle_contract() -> None:
    bundle = build_architecture(ROOT)
    assert bundle["kind"] == "archmap.bundle"
    assert bundle["schemaVersion"] == "6.0"
    assert bundle["project"]["name"] == "student_demo"
    assert len(bundle["projectGraph"]["modules"]) == 3
    assert len(bundle["functionDetails"]) == 5
    assert "functionFlows" not in bundle
    assert "callSites" in bundle
    assert bundle["entrypoints"] == [{"functionId": "fn:app.main.main", "reason": "configured"}]
    issues = validate_bundle(bundle)
    assert not [issue for issue in issues if issue["severity"] == "error"]


def test_function_details_have_source_and_call_contract() -> None:
    bundle = build_architecture(ROOT)
    details = {detail["name"]: detail for detail in bundle["functionDetails"]}
    for detail in details.values():
        assert detail["signature"].startswith(("def ", "async def "))
        assert detail["source"]["text"]
        assert detail["source"]["startLine"] <= detail["source"]["endLine"]
        assert detail["sourceHash"].startswith("sha256:")
        assert isinstance(detail["callers"], list)
        assert isinstance(detail["callees"], list)
    assert details["main"]["calleeCount"] >= 1
    assert details["main"]["source"]["endLine"] >= details["main"]["line"]


def test_notes_are_extracted_from_docstrings_and_comments() -> None:
    bundle = build_architecture(ROOT)
    details = {detail["name"]: detail for detail in bundle["functionDetails"]}
    assert details["main"]["note"] == "程序主入口，加载并处理学生数据。"
    assert details["save_item"]["note"] == "保存单个学生记录并返回结果"


def test_macro_cross_references() -> None:
    bundle = build_architecture(ROOT)
    detail_ids = {detail["id"] for detail in bundle["functionDetails"]}
    for module in bundle["projectGraph"]["modules"]:
        assert set(module["functions"]) <= detail_ids
    for graph in bundle["moduleGraphs"]:
        assert "edges" not in graph
        assert all(edge["from"] in detail_ids and edge["to"] in detail_ids for edge in graph["methodEdges"])


def test_fingerprint_is_stable_and_layout_independent() -> None:
    first = build_architecture(ROOT)
    second = build_architecture(ROOT)
    assert semantic_fingerprint(first) == semantic_fingerprint(second)
    second["moduleGraphs"][0]["layout"]["canvas"]["width"] += 1
    assert semantic_fingerprint(first) == semantic_fingerprint(second)


def test_bundle_matches_current_v6_schema() -> None:
    import json
    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    bundle = build_architecture(ROOT)
    schema_path = Path(__file__).parent.parent / "docs" / "schema" / "archmap-v6-bundle.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["schemaVersion"]["const"] == "6.0"
    jsonschema.validate(bundle, schema)


def test_archmap_v3_self_config_builds_cross_module_edges() -> None:
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(repo_root, config_path)
    assert len(bundle["projectGraph"]["modules"]) == 5
    internal_edges = [
        edge for edge in bundle["projectGraph"]["edges"] if edge["role"] == "internal"
    ]
    assert internal_edges
    module_ids = {module["id"] for module in bundle["projectGraph"]["modules"]}
    assert {"pipeline-entry", "python-frontend", "graph-projection", "validation", "rendering"} == module_ids
    roles = {module["id"]: module["role"] for module in bundle["projectGraph"]["modules"]}
    assert roles["pipeline-entry"] == "service"
    assert roles["python-frontend"] == "service"
    assert "core-contracts" not in module_ids
    assert "mainModuleId" not in bundle["projectGraph"]
    assert "mainFlows" not in bundle["projectGraph"]
    assert "primaryFlowId" not in bundle["projectGraph"]
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_call_sites_are_independent_from_removed_function_flows() -> None:
    bundle = build_architecture(ROOT)
    assert bundle["callSites"]
    for site in bundle["callSites"]:
        assert site["fromFunctionId"] in {detail["id"] for detail in bundle["functionDetails"]}
        assert "calleeText" in site
        assert "line" in site


def test_default_excludes_skip_root_level_build_directory(tmp_path: Path) -> None:
    (tmp_path / "build" / "lib").mkdir(parents=True)
    (tmp_path / "build" / "lib" / "generated.py").write_text("def generated():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    bundle = build_architecture(tmp_path)
    rel_paths = {detail["file"] for detail in bundle["functionDetails"]}
    assert "app.py" in rel_paths
    assert "build/lib/generated.py" not in rel_paths


def test_execution_edge_contract_is_tightened_and_v4_0_is_archived() -> None:
    import json
    from pathlib import Path as FilePath

    schema_dir = FilePath(__file__).parent.parent / "docs" / "schema"
    current = json.loads((schema_dir / "archmap-v4-bundle.schema.json").read_text(encoding="utf-8"))
    historical = json.loads(
        (schema_dir / "archmap-v4.0-bundle.schema.json").read_text(encoding="utf-8")
    )
    current_kinds = current["$defs"]["executionEdge"]["properties"]["kind"]["enum"]
    historical_kinds = historical["$defs"]["executionEdge"]["properties"]["kind"]["enum"]
    assert historical["properties"]["schemaVersion"]["const"] == "4.0"
    assert current["properties"]["schemaVersion"]["const"] == "4.1"
    assert {"break", "continue", "return", "back", "dispatch"} <= set(historical_kinds)
    assert current_kinds == [
        "next",
        "true",
        "false",
        "case",
        "default",
        "loop_body",
        "loop_complete",
    ]
