from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path

import pytest

from archmap.managers.pipeline_manager import PipelineManager

build_architecture = PipelineManager().build_architecture
REPO_ROOT = Path(__file__).parent.parent


def test_student_system_uses_vertical_capability_modules() -> None:
    """Student sample modules own their managers, models, config and utilities."""

    bundle = build_architecture(
        REPO_ROOT / "Projects" / "student_system",
        REPO_ROOT / "examples" / "student_system.archmap.json",
    )
    modules = {module["id"]: module for module in bundle["projectGraph"]["modules"]}
    assert set(modules) == {"app", "network", "database", "menu", "async-feedback", "test"}
    assert "contracts" not in modules
    assert modules["app"]["role"] == "service"
    assert all(module["role"] != "main" for module in modules.values())
    assert not bundle["diagnostics"]

    network = next(graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "network")
    network_nodes = {node["name"]: node for node in network["nodes"] if node["kind"] == "class"}
    assert network_nodes["ProtocolMessage"]["providerRole"] == "model"
    assert network_nodes["ProtocolMessage"]["providerVisibility"] == "public"
    assert network_nodes["ProtocolCodec"]["providerRole"] == "manager"
    codec_methods = {
        api["display"] for api in network_nodes["ProtocolCodec"]["providedApis"]
    }
    assert {"ProtocolCodec.encode(model: int, *args, **kwargs)", "ProtocolCodec.decode(received: bytes)"} <= codec_methods

    database = next(graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "database")
    database_nodes = {node["name"]: node for node in database["nodes"] if node["kind"] == "class"}
    assert database_nodes["DatabaseConfig"]["providerRole"] == "config"
    assert database_nodes["Database"]["providerRole"] == "adapter"

    menu = next(graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "menu")
    menu_nodes = {node["name"]: node for node in menu["nodes"] if node["kind"] == "class"}
    assert menu_nodes["StudentRecord"]["providerRole"] == "model"
    assert menu_nodes["StudentRecord"]["providerVisibility"] == "public"
    assert menu_nodes["MenuSystem"]["providerRole"] == "component"


def test_gomoku_has_no_main_module_and_no_module_call_view() -> None:
    """Gomoku uses entry/UI/application/domain/adapter modules without call lines."""

    configured_root = os.environ.get("ARCHMAP_GOMOKU_ROOT")
    gomoku_root = Path(configured_root) if configured_root else REPO_ROOT.parent / "五子棋"
    if not gomoku_root.exists():
        pytest.skip("gomoku sample source is not available in this workspace")
    bundle = build_architecture(
        gomoku_root,
        REPO_ROOT / "examples" / "gomoku.archmap.json",
    )
    modules = {module["id"]: module for module in bundle["projectGraph"]["modules"]}
    assert set(modules) == {"terminal", "terminal-ui", "application", "domain", "ai-adapter"}
    assert "main" not in modules and "entry" not in modules
    assert modules["terminal"]["role"] == "component"
    assert modules["terminal-ui"]["role"] == "component"
    terminal_graph = next(
        graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "terminal"
    )
    game_cli = next(
        node for node in terminal_graph["nodes"]
        if node.get("name") == "GameCli"
    )
    assert game_cli["providerRole"] == "component"
    assert bundle["projectGraph"]["flowCards"][0]["entrypointId"] == "fn:gomoku.cli.GameCli.run"
    assert not bundle["diagnostics"]
    assert all("edges" not in graph for graph in bundle["moduleGraphs"])
    project = bundle["projectGraph"]
    assert "mainModuleId" not in project
    assert "mainFlows" not in project
    assert "moduleKind" not in project["modules"][0]


def test_self_config_has_no_shared_contracts_module() -> None:
    """The self configuration dissolves the horizontal core-contracts bucket."""

    bundle = build_architecture(
        REPO_ROOT,
        REPO_ROOT / "examples" / "archmap_v3.archmap.json",
    )
    module_ids = {module["id"] for module in bundle["projectGraph"]["modules"]}
    assert module_ids == {
        "pipeline",
        "python-frontend",
        "graph-projection",
        "validation",
        "rendering",
    }
    assert "core-contracts" not in module_ids
    assert not bundle["diagnostics"]
    config = json.loads(
        (REPO_ROOT / "examples" / "archmap_v3.archmap.json").read_text(encoding="utf-8")
    )
    modules = config["modules"]
    for path in sorted((REPO_ROOT / "archmap").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        matches = [
            module["id"]
            for module in modules
            if any(
                fnmatch.fnmatch(rel, pattern)
                or fnmatch.fnmatch("/" + rel, pattern)
                for pattern in module["include"]
            )
        ]
        assert len(matches) == 1, f"{rel} must have exactly one module owner: {matches}"
