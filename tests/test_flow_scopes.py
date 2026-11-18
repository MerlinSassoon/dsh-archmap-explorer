"""P10 one-level execution-flow interface drilldown tests."""

from __future__ import annotations

from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent.parent


def _student_bundle() -> dict:
    return build_architecture(
        ROOT / "Projects" / "student_system",
        ROOT / "examples" / "student_system.archmap.json",
    )


def _gomoku_bundle() -> dict:
    return build_architecture(
        ROOT / "Projects" / "gomoku",
        ROOT / "examples" / "gomoku.archmap.json",
    )


def _scope_by_root(bundle: dict, root_function_id: str) -> dict:
    matches = [
        scope
        for flow in bundle["projectGraph"]["executionFlows"]
        for scope in flow.get("scopes", [])
        if scope.get("rootFunctionId") == root_function_id
    ]
    assert len(matches) == 1
    return matches[0]


def test_student_flow_scopes_drill_into_server_and_client() -> None:
    """Student server/client expose one-level module interfaces without recursion."""

    bundle = _student_bundle()
    assert bundle["schemaVersion"] == "6.3"
    assert bundle["stats"]["flowScopes"] >= 2
    issues = validate_bundle(bundle)
    assert not [issue for issue in issues if issue["severity"] == "error"]

    server = _scope_by_root(bundle, "fn:student_system.app.main.server")
    client = _scope_by_root(bundle, "fn:student_system.app.main.client")
    assert server["depth"] == 1
    assert client["depth"] == 1
    assert not server.get("scopes")
    assert not client.get("scopes")
    assert server["nodeCount"] <= 24
    assert client["nodeCount"] <= 24
    assert any("Database.actions" in item["label"] for item in server["interfaceSummary"])
    assert any("MenuSystem.run" in item["label"] for item in client["interfaceSummary"])
    assert not any(
        node.get("label", "").startswith("MenuSystem._add_student")
        for node in client["nodes"]
    )

    flow = bundle["projectGraph"]["executionFlows"][0]
    parent_nodes = {node["id"]: node for node in flow["nodes"]}
    for scope in (server, client):
        parent = parent_nodes[scope["parentNodeId"]]
        assert parent["drilldown"]["status"] == "available"
        assert parent["drilldown"]["scopeId"] == scope["id"]


def test_gomoku_play_one_game_scope_exposes_helper_interfaces() -> None:
    """Gomoku _play_one_game reveals game and renderer interfaces one level only."""

    bundle = _gomoku_bundle()
    scope = _scope_by_root(bundle, "fn:gomoku.cli.GameCli._play_one_game")
    assert scope["depth"] == 1
    assert not scope.get("scopes")
    assert scope["nodeCount"] <= 24

    labels = {item["label"] for item in scope["interfaceSummary"]}
    assert any("GomokuGame.play_ai_move" in label for label in labels)
    assert any("GomokuGame.play_human_move" in label for label in labels)
    assert any("BoardRenderer.render(" in label for label in labels)
    assert any(
        node.get("interfaceHints")
        for node in scope["nodes"]
        if node.get("kind") == "free_function"
    )
    assert not any(
        node.get("label", "").startswith("_apply_move")
        for node in scope["nodes"]
    )
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_flow_scopes_are_disabled_without_configuration() -> None:
    """Existing projects without flowScopes keep atomic call targets."""

    bundle = build_architecture(ROOT / "tests" / "fixtures" / "student_demo")
    for flow in bundle["projectGraph"]["executionFlows"]:
        assert flow.get("scopes", []) == []
        assert all("drilldown" not in node for node in flow["nodes"])

    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_validator_rejects_nested_or_deep_flow_scope() -> None:
    """Scope depth and nesting are hard contract limits."""

    bundle = _student_bundle()
    scope = _scope_by_root(bundle, "fn:student_system.app.main.server")
    scope["depth"] = 2
    scope["scopes"] = [{"id": "scope:nested"}]
    issues = validate_bundle(bundle)
    codes = {issue["code"] for issue in issues}
    assert "EXEC_SCOPE_DEPTH" in codes
    assert "EXEC_SCOPE_NESTED" in codes


def test_flow_scope_config_clamps_invalid_limits(tmp_path: Path) -> None:
    """Invalid scope budgets fall back with explicit configuration diagnostics."""

    from archmap.utility.config_utility import load_config

    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(
        """{
          "projectName": "scope-config",
          "flowScopes": {
            "enabled": true,
            "roots": ["app.main:run"],
            "autoDetect": false,
            "maxScopesPerFlow": -1,
            "maxNodesPerScope": "not-an-int",
            "maxEdgesPerScope": 999
          }
        }""",
        encoding="utf-8",
    )
    config = load_config(tmp_path, config_path)
    assert config.flow_scopes.enabled is True
    assert config.flow_scopes.roots == ["app.main:run"]
    assert config.flow_scopes.auto_detect is False
    assert config.flow_scopes.max_scopes_per_flow == 6
    assert config.flow_scopes.max_nodes_per_scope == 24
    assert config.flow_scopes.max_edges_per_scope == 120
    codes = {item["code"] for item in config.config_diagnostics}
    assert "FLOW_SCOPE_LIMIT_INVALID" in codes


def test_flow_scope_bundles_match_schema_6_3() -> None:
    """Student and gomoku scope projections satisfy the published schema."""

    import json

    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "docs" / "schema" / "archmap-v6.3-bundle.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(_student_bundle(), schema)
    jsonschema.validate(_gomoku_bundle(), schema)
