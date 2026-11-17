from __future__ import annotations

from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "class_demo"


def _graph(bundle: dict) -> dict:
    return bundle["moduleGraphs"][0]


def test_methods_are_owned_by_class_nodes_not_flattened() -> None:
    bundle = build_architecture(ROOT)
    graph = _graph(bundle)
    class_nodes = [node for node in graph["nodes"] if node["kind"] == "class"]
    function_nodes = [node for node in graph["nodes"] if node["kind"] == "function"]

    assert {node["name"] for node in class_nodes} == {"Worker", "EchoWorker"}
    assert {node["name"] for node in function_nodes} == {"make_worker"}
    method_ids = {
        method["id"]
        for node in class_nodes
        for method in node["methods"]
    }
    assert method_ids
    assert graph["methodCount"] == len(method_ids)
    assert not method_ids.intersection(node["id"] for node in graph["nodes"])

    for node in class_nodes:
        for method in node["methods"]:
            assert method["kind"] == "method"
            assert method["ownerClassId"] == node["id"]
            assert method["functionDetailId"] in {
                detail["id"] for detail in bundle["functionDetails"]
            }
    assert graph["methodEdges"]
    assert all(
        edge["from"] in method_ids and edge["to"] in method_ids
        for edge in graph["methodEdges"]
    )


def test_abstract_class_is_a_contract_not_a_flow_node() -> None:
    bundle = build_architecture(ROOT)
    graph = _graph(bundle)
    abstract = next(node for node in graph["nodes"] if node.get("name") == "Worker")
    assert abstract["classKind"] == "abstract"
    assert abstract["isAbstract"] is True
    assert abstract["entryMethodIds"] == []
    assert not any(edge["role"].startswith("module_") for edge in graph["edges"])
    flow_function_ids = {
        node["functionId"]
        for flow in bundle["projectGraph"]["mainFlows"]
        for node in flow["nodes"]
        if node.get("functionId")
    }
    assert "fn:app.worker.Worker.run" not in flow_function_ids


def test_module_graph_contains_providers_not_boundary_nodes() -> None:
    bundle = build_architecture(ROOT)
    graph = _graph(bundle)
    assert "inputs" not in graph
    assert "outputs" not in graph
    assert {node["kind"] for node in graph["nodes"]} <= {"class", "function"}
    component_ids = {node["id"] for node in graph["nodes"]}
    method_ids = {
        method["id"]
        for node in graph["nodes"]
        if node["kind"] == "class"
        for method in node["methods"]
    }
    assert not method_ids.intersection(component_ids)
    for edge in graph["edges"]:
        assert edge["from"] in component_ids
        assert edge["to"] in component_ids


def test_single_module_project_still_has_one_main_module() -> None:
    bundle = build_architecture(ROOT)
    modules = bundle["projectGraph"]["modules"]
    assert len(modules) == 1
    assert modules[0]["moduleKind"] == "main"
    assert bundle["projectGraph"]["mainModuleId"] == modules[0]["id"]
    assert not [module for module in modules if module["moduleKind"] == "functional"]


def test_function_detail_carries_method_ownership_and_source() -> None:
    bundle = build_architecture(ROOT)
    detail = next(detail for detail in bundle["functionDetails"] if detail["name"] == "run")
    assert detail["ownerClassId"] == "cls:app.worker.EchoWorker"
    assert detail["methodKind"] == "public_api"
    assert detail["visibility"] == "public"
    assert detail["source"]["text"]
    assert detail["sourceHash"].startswith("sha256:")
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]
