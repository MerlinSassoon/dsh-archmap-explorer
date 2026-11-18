from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "student_demo"
REPO_ROOT = Path(__file__).parent.parent


def _execution_flow(bundle: dict, entrypoint_id: str | None = None) -> dict:
    flows = bundle["projectGraph"]["executionFlows"]
    if entrypoint_id is None:
        return flows[0]
    return next(flow for flow in flows if flow["entrypointId"] == entrypoint_id)


def test_execution_flow_contract_uses_bounded_node_set() -> None:
    bundle = build_architecture(ROOT)
    flow = _execution_flow(bundle)
    kinds = {node["kind"] for node in flow["nodes"]}
    assert kinds <= {
        "entry", "exit", "free_function", "interface", "branch",
        "multi_branch", "loop", "break", "continue", "return",
        "dispatch",
    }
    assert {"entry", "interface", "loop", "branch", "return"} <= kinds
    assert "exit" not in kinds
    assert "merge" not in kinds
    return_nodes = [node for node in flow["nodes"] if node["kind"] == "return"]
    assert return_nodes
    assert all(
        not [edge for edge in flow["edges"] if edge["from"] == node["id"]]
        for node in return_nodes
    )
    assert all(node["expandable"] is False for node in flow["nodes"])
    assert all(edge["kind"] not in {"call", "call_path", "composition"} for edge in flow["edges"])
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_execution_flow_does_not_expand_interface_internals() -> None:
    bundle = build_architecture(ROOT)
    flow = _execution_flow(bundle)
    labels = {node["label"] for node in flow["nodes"]}
    assert {"load_items()", "save_item(item)"} <= labels
    assert "read_all()" not in labels
    assert "write_one(item)" not in labels
    loop = next(node for node in flow["nodes"] if node["kind"] == "loop")
    loop_ports = flow["layout"]["nodes"][loop["id"]]["ports"]
    assert set(loop_ports) == {"in", "loop_body", "loop_complete"}
    assert not any(edge["kind"] == "back" for edge in flow["edges"])
    assert any(node["kind"] == "branch" for node in flow["nodes"])


def test_student_system_execution_flow_keeps_free_functions_opaque() -> None:
    config = REPO_ROOT / "examples" / "student_system.archmap.json"
    bundle = build_architecture(REPO_ROOT / "Projects" / "student_system", config)
    flow = _execution_flow(bundle, "fn:student_system.main.main")
    nodes = {node["id"]: node for node in flow["nodes"]}
    labels = {node["label"] for node in flow["nodes"]}
    kinds = {node["kind"] for node in flow["nodes"]}
    assert {"main()", "NetworkAdapter.init_connection()", "server()", "client()"} <= labels
    assert {"multi_branch", "loop", "branch", "break"} <= kinds
    assert "with Spinner(message: str='加载中')" not in labels
    assert "with Database(password: str)" not in labels
    assert "Database.actions(client_input: bytes)" not in labels
    assert "MenuSystem.run()" not in labels
    assert not any(edge["kind"] == "loop_complete" for edge in flow["edges"])
    server = next(node for node in flow["nodes"] if node["label"] == "server()")
    client = next(node for node in flow["nodes"] if node["label"] == "client()")
    assert server["kind"] == "free_function"
    assert client["kind"] == "free_function"
    assert server["expandable"] is False
    assert client["expandable"] is False
    assert all(node["kind"] not in {"action", "statement", "provider", "merge"} for node in flow["nodes"])
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_execution_flow_layout_is_non_overlapping_and_orthogonal() -> None:
    bundle = build_architecture(ROOT)
    flow = _execution_flow(bundle)
    layout_nodes = flow["layout"]["nodes"]
    items = list(layout_nodes.items())
    for index, (first_id, first) in enumerate(items):
        for second_id, second in items[index + 1:]:
            separated = (
                first["x"] + first["w"] <= second["x"]
                or second["x"] + second["w"] <= first["x"]
                or first["y"] + first["h"] <= second["y"]
                or second["y"] + second["h"] <= first["y"]
            )
            assert separated, f"{first_id} overlaps {second_id}"
    import re
    for payload in flow["layout"]["edges"].values():
        assert payload["d"].startswith("M ")
        commands = set(re.findall(r"[A-Za-z]", payload["d"]))
        assert commands <= {"M", "C", "L"}
        assert payload["fromPort"]
        assert payload["toPort"]
    for position in layout_nodes.values():
        assert "in" in position["ports"] or position["ports"]


def test_execution_flow_call_sites_are_instance_scoped() -> None:
    bundle = build_architecture(ROOT)
    flow = _execution_flow(bundle)
    call_nodes = [node for node in flow["nodes"] if node["kind"] == "interface"]
    assert call_nodes
    assert len({node["callSiteId"] for node in call_nodes}) == len(call_nodes)
    for node in call_nodes:
        assert node["targetFunctionId"]
        assert node["capabilityId"]

def test_continuing_branches_fan_in_directly_without_merge(tmp_path: Path) -> None:
    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        """def step_a():
    pass


def step_b():
    pass


def main():
    if cond():
        step_a()
    else:
        step_b()
    step_a()
""",
        encoding="utf-8",
    )
    config = project / "archmap.config.json"
    config.write_text(
        """{
  "projectName": "fanin_demo",
  "language": "python",
  "include": ["app/*.py"],
  "entrypoints": ["main:main"],
  "modules": [
    {"id": "entry", "name": "入口", "include": ["app/main.py"], "kind": "main", "role": "main"}
  ],
  "mainModule": "entry"
}
""",
        encoding="utf-8",
    )
    bundle = build_architecture(project, config)
    flow = _execution_flow(bundle)
    nodes = {node["id"]: node for node in flow["nodes"]}
    assert all(node["kind"] != "merge" for node in flow["nodes"])
    fan_in_nodes = [
        node
        for node in flow["nodes"]
        if len([edge for edge in flow["edges"] if edge["to"] == node["id"]]) > 1
    ]
    assert fan_in_nodes
    fan_in = next(node for node in fan_in_nodes if node["kind"] == "free_function")
    incoming = [edge for edge in flow["edges"] if edge["to"] == fan_in["id"]]
    assert len(incoming) == 2
    assert {nodes[edge["from"]]["label"] for edge in incoming} == {"step_a()", "step_b()"}
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_execution_entrypoint_can_target_a_main_module_method(tmp_path: Path) -> None:
    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        """def step() -> bool:
    return True


def helper() -> None:
    pass


class Runner:
    def run(self) -> int:
        while True:
            mode = self._choose_mode()
            if mode is None:
                return 0
            self._play_one_game(mode)

    def _choose_mode(self):
        return "human-vs-ai"

    def _play_one_game(self, mode: str) -> None:
        helper()


def main() -> int:
    return Runner().run()
""",
        encoding="utf-8",
    )
    config = {
        "projectName": "execution_entrypoint_demo",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "executionEntrypoints": ["app.main:Runner.run"],
        "mainModule": "main",
        "modules": [
            {
                "id": "main",
                "name": "主模块",
                "include": ["app/*.py"],
                "role": "main",
                "kind": "main",
            }
        ],
    }
    config_path = project / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    bundle = build_architecture(project, config_path)

    assert bundle["entrypoints"] == [
        {"functionId": "fn:app.main.main", "reason": "configured"}
    ]
    assert bundle["projectGraph"]["executionEntrypoints"] == [
        {"functionId": "fn:app.main.Runner.run", "reason": "execution-configured"}
    ]
    flow = _execution_flow(bundle, "fn:app.main.Runner.run")
    assert flow["name"] == "run()"
    assert flow["entrypointReason"] == "execution-configured"
    kinds = {node["kind"] for node in flow["nodes"]}
    assert {"loop", "branch", "return"} <= kinds
    assert "exit" not in kinds
    assert next(node for node in flow["nodes"] if node["kind"] == "entry")[
        "functionId"
    ] == "fn:app.main.Runner.run"
    labels = {node["label"] for node in flow["nodes"]}
    assert {"_choose_mode()", "_play_one_game()"} <= labels
    assert "helper()" not in labels
    method_nodes = [
        node
        for node in flow["nodes"]
        if node["kind"] == "free_function" and node.get("callableKind") == "method"
    ]
    assert {node["label"] for node in method_nodes} == {
        "_choose_mode()",
        "_play_one_game()",
    }
    assert all(node["ownerClassName"] == "Runner" for node in method_nodes)
    assert all(node["expandable"] is False for node in method_nodes)
    return_nodes = [node for node in flow["nodes"] if node["kind"] == "return"]
    assert return_nodes
    assert all(
        not [edge for edge in flow["edges"] if edge["from"] == node["id"]]
        for node in return_nodes
    )
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_implicit_fallthrough_still_uses_exit(tmp_path: Path) -> None:
    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        """def step() -> None:
    pass


def main() -> None:
    step()
""",
        encoding="utf-8",
    )
    config = {
        "projectName": "fallthrough_demo",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "mainModule": "main",
        "modules": [
            {
                "id": "main",
                "name": "主模块",
                "include": ["app/*.py"],
                "role": "main",
                "kind": "main",
            }
        ],
    }
    config_path = project / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    flow = _execution_flow(build_architecture(project, config_path))
    exit_node = next(node for node in flow["nodes"] if node["kind"] == "exit")
    step_node = next(node for node in flow["nodes"] if node["label"] == "step()")
    assert any(
        edge["from"] == step_node["id"] and edge["to"] == exit_node["id"]
        for edge in flow["edges"]
    )


def test_unresolved_execution_entrypoint_falls_back_with_diagnostic(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        """def main() -> int:
    return 0
""",
        encoding="utf-8",
    )
    config = {
        "projectName": "execution_entrypoint_fallback",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "executionEntrypoints": ["app.main:Missing.run"],
        "mainModule": "main",
        "modules": [
            {
                "id": "main",
                "name": "主模块",
                "include": ["app/*.py"],
                "role": "main",
                "kind": "main",
            }
        ],
    }
    config_path = project / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    bundle = build_architecture(project, config_path)

    flow = _execution_flow(bundle, "fn:app.main.main")
    assert flow["name"] == "main()"
    codes = {item["code"] for item in bundle["diagnostics"]}
    assert "EXECUTION_ENTRYPOINT_UNRESOLVED" in codes
    assert "EXECUTION_ENTRYPOINT_FALLBACK" in codes
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]
