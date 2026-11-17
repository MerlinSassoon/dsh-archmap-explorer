from __future__ import annotations

from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "student_demo"
DISPATCH_ROOT = Path(__file__).parent / "fixtures" / "dispatch_demo"
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"
REPO_ROOT = Path(__file__).parent.parent


def _flow(bundle: dict, entrypoint_id: str | None = None) -> dict:
    flows = bundle["projectGraph"]["mainFlows"]
    if entrypoint_id is None:
        return flows[0]
    return next(flow for flow in flows if flow["entrypointId"] == entrypoint_id)


def test_modules_have_no_input_output_nodes_or_edges() -> None:
    bundle = build_architecture(ROOT)
    project = bundle["projectGraph"]
    assert "boundaryNodes" not in project
    assert "inputs" not in project["project"]
    assert "outputs" not in project["project"]
    for module in project["modules"]:
        assert "inputs" not in module
        assert "outputs" not in module
    for graph in bundle["moduleGraphs"]:
        assert "inputs" not in graph
        assert "outputs" not in graph
        assert {node["kind"] for node in graph["nodes"]} <= {"class", "function"}
        assert all(edge["role"] == "internal" for edge in graph["edges"])
    assert all(edge["role"] == "internal" for edge in project["edges"])


def test_main_flow_contains_entry_and_functional_interfaces() -> None:
    bundle = build_architecture(ROOT)
    flow = _flow(bundle)
    nodes = {node["id"]: node for node in flow["nodes"]}
    labels = {node["label"] for node in nodes.values()}
    assert flow["entrypointId"] == "fn:app.main.main"
    assert next(node for node in nodes.values() if node["kind"] == "entry")["isEntry"] is True
    assert {"main()", "load_items()", "save_item(item)"} <= labels
    assert "read_all()" not in labels
    assert "write_one(item)" not in labels
    assert flow["edges"]
    assert all(edge["kind"] in {"call", "call_path", "composition"} for edge in flow["edges"])
    assert all(edge["confidence"] == "high" for edge in flow["edges"] if edge["kind"] == "call")
    for node in flow["nodes"]:
        if node["kind"] == "interface":
            assert node.get("capabilityId")
            assert not str(node["capabilityId"]).startswith("flow-capability:")
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_student_system_main_flow_models_server_client_branches() -> None:
    config = REPO_ROOT / "examples" / "student_system.archmap.json"
    bundle = build_architecture(REPO_ROOT / "Projects" / "student_system", config)
    flow = _flow(bundle, "fn:student_system.main.main")
    nodes = {node["id"]: node for node in flow["nodes"]}
    labels = {node["label"] for node in nodes.values()}
    kinds = {node["kind"] for node in nodes.values()}
    assert {"entry", "orchestrator", "provider", "interface"} <= kinds
    assert {"main()", "NetworkAdapter.init_connection()", "server()", "client()"} <= labels
    assert {"Spinner", "Database", "MenuSystem"} <= labels
    assert {"Database.actions(client_input: bytes)", "MenuSystem.run()"} <= labels
    assert "NetworkAdapter.create_server(local_ip: str)" not in labels
    assert "NetworkAdapter.connect_to_server(local_ip: str)" not in labels
    assert "decode_message()" not in labels
    assert "get_display_width()" not in labels
    boundary_nodes = [node for node in flow["nodes"] if node.get("flowBoundary")]
    assert boundary_nodes
    assert all(node["kind"] in {"interface", "provider"} for node in boundary_nodes)
    assert all(node.get("expandable") is False for node in boundary_nodes)
    boundary_ids = {node["id"] for node in boundary_nodes}
    assert not any(edge["from"] in boundary_ids for edge in flow["edges"])
    server_edges = [
        edge for edge in flow["edges"]
        if nodes[edge["from"]]["label"] == "main()" and nodes[edge["to"]]["label"] == "server()"
    ]
    client_edges = [
        edge for edge in flow["edges"]
        if nodes[edge["from"]]["label"] == "main()" and nodes[edge["to"]]["label"] == "client()"
    ]
    assert server_edges and server_edges[0]["branchLabel"] == "model == 'SERVER'"
    assert client_edges and client_edges[0]["branchLabel"] == "model == 'CLIENT'"
    for forbidden in {"while", "try", "input()", "print()", "sockets.recv"}:
        assert forbidden not in labels
    assert all(edge["kind"] != "composition" for edge in flow["edges"])
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_dispatch_candidates_are_dashed_low_composition_edges() -> None:
    bundle = build_architecture(DISPATCH_ROOT)
    flow = _flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert dispatch["candidateCount"] == 2
    assert dispatch["candidateSetComplete"] is False
    assert dispatch["candidateSource"] == "static_registry"
    candidate_edges = [edge for edge in flow["edges"] if edge["from"] == dispatch["id"]]
    assert len(candidate_edges) == 2
    assert all(edge["kind"] == "composition" for edge in candidate_edges)
    assert all(edge["confidence"] == "low" for edge in candidate_edges)
    assert all(edge["dashed"] is True for edge in candidate_edges)
    assert all(edge["candidateSource"] == "static_registry" for edge in candidate_edges)
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_explicit_dispatch_config_can_be_complete() -> None:
    config = REPO_ROOT / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(REPO_ROOT, config)
    flow = _flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert dispatch["candidateSource"] == "config"
    assert dispatch["candidateSetComplete"] is True
    assert dispatch["candidateCount"] == 5
    candidate_edges = [edge for edge in flow["edges"] if edge["from"] == dispatch["id"]]
    assert len(candidate_edges) == 5
    assert all(edge["kind"] == "composition" and edge["confidence"] == "low" for edge in candidate_edges)
    assert all(edge["dashed"] is True for edge in candidate_edges)


def test_main_flow_does_not_mutate_functional_provider_roles() -> None:
    bundle = build_architecture(ROOT)
    service_graph = next(graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "service")
    api_providers = {provider["providerName"]: provider for provider in service_graph["apiProviders"]}
    assert set(api_providers) == {"load_items", "save_item"}
    assert {provider["providerRole"] for provider in api_providers.values()} == {"manager"}
    flow = _flow(bundle)
    assert any(node["moduleId"] == "service" and node["kind"] == "interface" for node in flow["nodes"])


def test_single_module_project_has_zero_functional_modules_and_a_flow() -> None:
    bundle = build_architecture(CLASS_ROOT)
    modules = bundle["projectGraph"]["modules"]
    assert len(modules) == 1
    assert modules[0]["moduleKind"] == "main"
    assert bundle["projectGraph"]["mainModuleId"] == modules[0]["id"]
    assert bundle["projectGraph"]["mainFlows"]
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_validator_rejects_multiple_main_modules_and_high_confidence_composition() -> None:
    bundle = build_architecture(ROOT)
    bundle["projectGraph"]["modules"][1]["moduleKind"] = "main"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "MAIN_MODULE_COUNT" for issue in issues)

    bundle = build_architecture(DISPATCH_ROOT)
    flow = _flow(bundle)
    composition = next(edge for edge in flow["edges"] if edge["kind"] == "composition")
    composition["confidence"] = "high"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "FLOW_COMPOSITION_CONFIDENCE" for issue in issues)


def test_inline_dispatch_comment_can_declare_complete_candidates(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''def handler_a():\n    return "a"\n\n\ndef handler_b():\n    return "b"\n\n\ndef main(mode):\n    handlers = {}\n    # archmap:dispatch complete=true candidates=handler_a,handler_b\n    return handlers[mode]()\n''',
        encoding="utf-8",
    )
    config = {
        "projectName": "comment_dispatch",
        "language": "python",
        "include": ["app/*.py"],
        "mainModule": "main",
        "entrypoints": ["app.main:main"],
        "modules": [
            {
                "id": "main",
                "name": "主流程",
                "kind": "main",
                "include": ["app/main.py"],
                "role": "main",
            }
        ],
    }
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(__import__("json").dumps(config), encoding="utf-8")
    bundle = build_architecture(tmp_path, config_path)
    flow = _flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert dispatch["candidateSource"] == "comment"
    assert dispatch["candidateSetComplete"] is True
    assert dispatch["candidateCount"] == 2
    candidate_edges = [edge for edge in flow["edges"] if edge["from"] == dispatch["id"]]
    assert len(candidate_edges) == 2
    assert all(edge["kind"] == "composition" and edge["confidence"] == "low" for edge in candidate_edges)


def test_student_system_sample_is_normalized_to_four_code_units() -> None:
    project = REPO_ROOT / "Projects" / "student_system"
    assert (project / "student_system" / "main.py").exists()
    assert (project / "student_system" / "config" / "database_config.py").exists()
    assert (project / "student_system" / "model" / "student_model.py").exists()
    assert (project / "student_system" / "managers" / "database_manager.py").exists()
    assert (project / "student_system" / "utility" / "protocol_utility.py").exists()
    assert not (project / "database.py").exists()
    assert not (project / "menu_system.py").exists()
    assert not (project / "TcpConnect.py").exists()

    config = REPO_ROOT / "examples" / "student_system.archmap.json"
    bundle = build_architecture(project, config)
    modules = bundle["projectGraph"]["modules"]
    assert len(modules) == 7
    assert [module["id"] for module in modules if module["moduleKind"] == "main"] == ["main"]
    assert {module["id"] for module in modules if module["moduleKind"] == "functional"} == {
        "network",
        "database",
        "menu",
        "async",
        "contracts",
        "test",
    }
    provider_roles = {
        provider["providerName"]: provider["providerRole"]
        for graph in bundle["moduleGraphs"]
        for provider in graph["apiProviders"]
    }
    assert provider_roles["NetworkAdapter"] == "adapter"
    assert provider_roles["Database"] == "adapter"
    assert provider_roles["MenuSystem"] == "component"
    assert provider_roles["Spinner"] == "component"
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_validator_rejects_noncanonical_flow_interface() -> None:
    bundle = build_architecture(ROOT)
    flow = _flow(bundle)
    interface = next(node for node in flow["nodes"] if node["kind"] == "interface")
    interface["capabilityId"] = "api:missing"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "FLOW_INTERFACE_NOT_CANONICAL" for issue in issues)


def test_self_main_flow_stops_at_functional_module_interfaces() -> None:
    config = REPO_ROOT / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(REPO_ROOT, config)
    flow = _flow(bundle)
    labels = {node["label"] for node in flow["nodes"]}
    assert "ValidationManager.validate(bundle: dict[str, Any])" in labels
    assert "RenderManager.render(bundle: dict[str, Any], annotations: dict[str, Any] | None=None)" in labels
    assert "validate_bundle()" not in labels
    assert "render_html()" not in labels
    assert "load_config()" not in labels
    assert "build_main_flows()" not in labels
    boundary_ids = {node["id"] for node in flow["nodes"] if node.get("flowBoundary")}
    assert boundary_ids
    assert not any(edge["from"] in boundary_ids for edge in flow["edges"])
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]
