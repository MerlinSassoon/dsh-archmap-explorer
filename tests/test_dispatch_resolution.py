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


def test_project_modules_have_no_main_module_or_io_ports() -> None:
    """Schema 5.0 project modules are ordinary capability units."""

    bundle = build_architecture(ROOT)
    project = bundle["projectGraph"]
    assert "mainModuleId" not in project
    assert "mainFlows" not in project
    assert "primaryFlowId" not in project
    for module in project["modules"]:
        assert "moduleKind" not in module
        assert "inputs" not in module
        assert "outputs" not in module
        assert module["role"] in {"service", "adapter", "component", "entry", "test", "other"}


def test_execution_flow_dispatches_use_config_complete_candidates() -> None:
    """Configured dispatch hints must populate execution-flow dispatch nodes."""

    config = REPO_ROOT / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(REPO_ROOT, config)
    flow = _execution_flow(bundle, "fn:archmap.entry.cli_entry.main")
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert dispatch["candidateSource"] == "config"
    assert dispatch["candidateSetComplete"] is True
    assert dispatch["candidateCount"] == 11
    assert len(dispatch["candidates"]) == 11
    assert all(edge["kind"] != "composition" for edge in flow["edges"])


def test_inline_dispatch_comment_reaches_execution_flow(tmp_path: Path) -> None:
    """Inline dispatch declarations must resolve through the shared resolver."""

    app = tmp_path / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''def handler_a():\n    return "a"\n\n\ndef handler_b():\n    return "b"\n\n\ndef main(mode):\n    handlers = {}\n    # archmap:dispatch complete=true candidates=handler_a,handler_b\n    return handlers[mode]()\n''',
        encoding="utf-8",
    )
    config = {
        "projectName": "comment_dispatch",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "modules": [
            {"id": "app", "name": "应用", "include": ["app/main.py"], "role": "entry"}
        ],
    }
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    bundle = build_architecture(tmp_path, config_path)
    flow = _execution_flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert dispatch["candidateSource"] == "comment"
    assert dispatch["candidateSetComplete"] is True
    assert dispatch["candidateCount"] == 2
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_dispatch_hints_support_top_level_config_key(tmp_path: Path) -> None:
    """Top-level dispatchHints is the canonical schema 5.0 configuration key."""

    app = tmp_path / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''def handler_a():\n    return "a"\n\n\ndef handler_b():\n    return "b"\n\n\ndef main(mode):\n    handlers = {}\n    return handlers[mode]()\n''',
        encoding="utf-8",
    )
    config = {
        "projectName": "top_level_dispatch",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "dispatchHints": [
            {
                "function": "app.main:main",
                "expression": "handlers[mode]",
                "candidates": ["app.main:handler_a", "app.main:handler_b"],
                "complete": True,
                "reason": "config",
            }
        ],
        "modules": [
            {"id": "app", "name": "应用", "include": ["app/main.py"], "role": "entry"}
        ],
    }
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    bundle = build_architecture(tmp_path, config_path)
    dispatch = next(
        node for node in _execution_flow(bundle)["nodes"]
        if node["kind"] == "dispatch"
    )
    assert dispatch["candidateCount"] == 2
    assert dispatch["candidateSetComplete"] is True
    assert dispatch["candidateSource"] == "config"


def test_self_execution_flow_uses_bounded_call_steps() -> None:
    """The self flow keeps calls atomic and does not expand module internals."""

    config = REPO_ROOT / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(REPO_ROOT, config)
    flow = _execution_flow(bundle, "fn:archmap.entry.cli_entry.main")
    assert flow["nodes"]
    assert {node["kind"] for node in flow["nodes"]} <= {
        "entry", "exit", "free_function", "interface", "branch", "multi_branch",
        "loop", "break", "continue", "return", "dispatch",
    }
    assert all(node["expandable"] is False for node in flow["nodes"])
    assert all(edge["kind"] != "composition" for edge in flow["edges"])
