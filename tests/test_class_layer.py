from __future__ import annotations

from pathlib import Path

from archmap.pipeline import build_architecture
from archmap.validate import validate_bundle

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


def test_abstract_class_is_a_contract_not_a_module_boundary() -> None:
    bundle = build_architecture(ROOT)
    graph = _graph(bundle)
    abstract = next(node for node in graph["nodes"] if node.get("name") == "Worker")
    assert abstract["classKind"] == "abstract"
    assert abstract["isAbstract"] is True
    assert abstract["entryMethodIds"] == []
    boundary_edges = [
        edge for edge in graph["edges"] if edge["role"].startswith("module_")
    ]
    assert all(edge["from"] != abstract["id"] and edge["to"] != abstract["id"] for edge in boundary_edges)


def test_module_boundary_edges_only_target_components() -> None:
    bundle = build_architecture(ROOT)
    graph = _graph(bundle)
    component_ids = {
        node["id"]
        for node in graph["nodes"]
        if node["kind"] in {"class", "function", "input", "output"}
    }
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


def test_class_boundary_has_via_method_evidence() -> None:
    bundle = build_architecture(ROOT)
    graph = _graph(bundle)
    echo = next(node for node in graph["nodes"] if node.get("name") == "EchoWorker")
    input_edge = next(
        edge for edge in graph["edges"]
        if edge["role"] == "module_input" and edge["to"] == echo["id"]
    )
    assert input_edge["viaMethodIds"] == ["fn:app.worker.EchoWorker.run"]
    assert echo["entryMethodIds"] == ["fn:app.worker.EchoWorker.run"]


def test_function_detail_carries_method_ownership_and_source() -> None:
    bundle = build_architecture(ROOT)
    detail = next(detail for detail in bundle["functionDetails"] if detail["name"] == "run")
    assert detail["ownerClassId"] == "cls:app.worker.EchoWorker"
    assert detail["methodKind"] == "public_api"
    assert detail["visibility"] == "public"
    assert detail["source"]["text"]
    assert detail["sourceHash"].startswith("sha256:")
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]
