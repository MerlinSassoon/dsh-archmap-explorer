from __future__ import annotations

from pathlib import Path

from archmap.graph import semantic_fingerprint
from archmap.pipeline import build_architecture
from archmap.validate import validate_bundle

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def test_build_bundle_contract() -> None:
    bundle = build_architecture(ROOT)
    assert bundle["kind"] == "archmap.bundle"
    assert bundle["schemaVersion"] == "3.0"
    assert bundle["project"]["name"] == "student_demo"
    assert len(bundle["projectGraph"]["modules"]) == 3
    assert len(bundle["functionFlows"]) == 5
    assert bundle["entrypoints"] == [{"functionId": "fn:app.main.main", "reason": "configured"}]
    issues = validate_bundle(bundle)
    assert not [issue for issue in issues if issue["severity"] == "error"]


def test_each_function_has_one_entry_and_exit_and_only_two_edge_types() -> None:
    bundle = build_architecture(ROOT)
    for flow in bundle["functionFlows"]:
        nodes = flow["nodes"]
        assert sum(node["type"] == "entry" for node in nodes) == 1
        assert sum(node["type"] == "exit" for node in nodes) == 1
        assert {edge["type"] for edge in flow["edges"]} <= {"next_step", "data_dep"}


def test_notes_are_extracted_from_docstrings_and_comments() -> None:
    bundle = build_architecture(ROOT)
    flows = {flow["name"]: flow for flow in bundle["functionFlows"]}
    assert flows["main"]["note"] == "程序主入口，加载并处理学生数据。"
    assert flows["save_item"]["note"] == "保存单个学生记录并返回结果"


def test_macro_cross_references() -> None:
    bundle = build_architecture(ROOT)
    flow_ids = {flow["id"] for flow in bundle["functionFlows"]}
    for module in bundle["projectGraph"]["modules"]:
        assert set(module["functions"]) <= flow_ids
    for graph in bundle["moduleGraphs"]:
        node_ids = {node["id"] for node in graph["nodes"]}
        assert all(edge["from"] in node_ids and edge["to"] in node_ids for edge in graph["edges"])


def test_fingerprint_is_stable_and_layout_independent() -> None:
    first = build_architecture(ROOT)
    second = build_architecture(ROOT)
    assert semantic_fingerprint(first) == semantic_fingerprint(second)
    second["functionFlows"][0]["layout"]["canvas"]["width"] += 1
    assert semantic_fingerprint(first) == semantic_fingerprint(second)


def test_bundle_matches_v3_schema() -> None:
    import json
    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    bundle = build_architecture(ROOT)
    schema_path = Path(__file__).parent.parent / "docs" / "schema" / "archmap-v3-bundle.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(bundle, schema)


def test_archmap_v3_self_config_builds_cross_module_edges() -> None:
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(repo_root, config_path)
    assert len(bundle["projectGraph"]["modules"]) == 6
    internal_edges = [
        edge for edge in bundle["projectGraph"]["edges"] if edge["role"] == "internal"
    ]
    assert internal_edges
    module_ids = {module["id"] for module in bundle["projectGraph"]["modules"]}
    assert {"cli-pipeline", "python-frontend", "flow-build", "graph-projection", "layout-routing", "validate-render"} <= module_ids
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_default_excludes_skip_root_level_build_directory(tmp_path: Path) -> None:
    from archmap.config import load_config
    from archmap.discover import discover_sources

    (tmp_path / "build" / "lib").mkdir(parents=True)
    (tmp_path / "build" / "lib" / "generated.py").write_text("def generated():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    config = load_config(tmp_path)
    rel_paths = {source.rel_path for source in discover_sources(config)}
    assert "app.py" in rel_paths
    assert "build/lib/generated.py" not in rel_paths
