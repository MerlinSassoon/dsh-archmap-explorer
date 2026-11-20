from __future__ import annotations

import json
from pathlib import Path

from archmap.config.contract_config import PROVIDER_ROLES
from archmap.config.project_config import MODULE_ROLES
from archmap.managers.pipeline_manager import PipelineManager

build_architecture = PipelineManager().build_architecture
REPO_ROOT = Path(__file__).parent.parent


def test_provider_and_module_roles_exclude_entry() -> None:
    """Entry is a flow concept, not a provider or module role."""

    assert "entry" not in PROVIDER_ROLES
    assert "entry" not in MODULE_ROLES
    assert PROVIDER_ROLES == {
        "config", "model", "manager", "adapter", "component", "contract", "utility"
    }


def test_entry_role_override_is_deprecated_without_changing_provider_role(tmp_path: Path) -> None:
    """Legacy entry role overrides warn and are ignored by Provider Role inference."""

    app = tmp_path / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''def main():\n    """Program entry."""\n    return 1\n''',
        encoding="utf-8",
    )
    config = {
        "projectName": "entry_role_compat",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "modules": [
            {"id": "app", "name": "应用", "include": ["app/main.py"]}
        ],
        "contract": {"providerRoles": {"app.main.main": "entry"}},
    }
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    bundle = build_architecture(tmp_path, config_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")
    assert detail["isFlowEntry"] is True
    assert detail.get("providerRole") != "entry"
    assert any(
        item["code"] == "PROVIDER_ENTRY_ROLE_DEPRECATED"
        for item in bundle["diagnostics"]
    )


def test_student_flow_entries_are_not_provider_roles() -> None:
    """Student flow entrypoints remain function facts without entry provider role."""

    bundle = build_architecture(
        REPO_ROOT / "examples" / "student_system",
        REPO_ROOT / "examples" / "student_system" / "archmap.config.json",
    )
    main = next(
        item for item in bundle["functionDetails"]
        if item["id"] == "fn:student_system.app.main.main"
    )
    assert main["isFlowEntry"] is True
    assert main["isExecutionOnly"] is True
    assert main["functionSurface"] == "execution"
    assert main["executionRole"] == "entry"
    assert "providerRole" not in main
    assert "entry" not in bundle["stats"]["providerRoles"]


def test_execution_flow_requires_one_standard_entry_node() -> None:
    """Execution flow validation must require exactly one entry node."""

    from archmap.managers.validate_manager import ValidationManager

    bundle = build_architecture(REPO_ROOT / "tests" / "fixtures" / "student_demo")
    flow = bundle["projectGraph"]["executionFlows"][0]
    entry = next(node for node in flow["nodes"] if node["kind"] == "entry")
    assert entry["functionId"] == flow["entrypointId"]
    flow["nodes"] = [node for node in flow["nodes"] if node["kind"] != "entry"]
    issues = ValidationManager().validate(bundle)
    assert any(issue["code"] == "EXEC_ENTRY_COUNT" for issue in issues)


def test_project_flow_cards_share_module_card_grid() -> None:
    """Flow cards are project page items in the same layout as module cards."""

    bundle = build_architecture(REPO_ROOT / "tests" / "fixtures" / "student_demo")
    project = bundle["projectGraph"]
    flow_cards = project["flowCards"]
    assert len(flow_cards) == len(project["executionFlows"]) == 1
    card = flow_cards[0]
    assert card["kind"] == "flow"
    assert card["flowId"] == project["primaryExecutionFlowId"]
    assert card["entrypointId"] == project["executionFlows"][0]["entrypointId"]
    assert card["id"] in project["layout"]["nodes"]
    module_ids = {module["id"] for module in project["modules"]}
    assert card["id"] not in module_ids
    assert set(project["layout"]["nodes"]) == module_ids | {card["id"]}


def test_entrypoints_are_flow_facts_not_module_capability_roles() -> None:
    """Flow entrypoints keep source ownership but no module-level entry role."""

    bundle = build_architecture(
        REPO_ROOT / "examples" / "student_system",
        REPO_ROOT / "examples" / "student_system" / "archmap.config.json",
    )
    for graph in bundle["moduleGraphs"]:
        assert "entry" not in graph["moduleComposition"]
        assert all(api["providerRole"] != "entry" for api in graph["providedApis"])
        assert all(
            node.get("providerRole") != "entry"
            for node in graph["nodes"]
            if node.get("kind") in {"class", "function"}
        )
    app = next(
        graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "app"
    )
    assert app["flowEntryFunctionIds"] == ["fn:student_system.app.main.main"]
    assert "fn:student_system.app.main.main" in app["entryFunctionIds"]
