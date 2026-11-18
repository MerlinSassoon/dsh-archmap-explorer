from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate
REPO_ROOT = Path(__file__).parent.parent


def _student_bundle() -> dict:
    return build_architecture(
        REPO_ROOT / "Projects" / "student_system",
        REPO_ROOT / "examples" / "student_system.archmap.json",
    )


def test_execution_only_callables_are_transparent_to_capability_surface() -> None:
    """Flow-only free functions stay in facts and flows but leave module APIs."""

    bundle = _student_bundle()
    app_graph = next(
        graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == "app"
    )
    expected = {
        "fn:student_system.app.main.client",
        "fn:student_system.app.main.main",
        "fn:student_system.app.main.server",
    }
    assert set(app_graph["executionOnlyFunctionIds"]) == expected
    assert app_graph["capabilitySurface"] == {
        "hasProviders": False,
        "providerCount": 0,
        "apiCount": 0,
    }
    assert not [
        api for api in app_graph["providedApis"]
        if api.get("functionId") in expected
    ]
    assert not [
        node for node in app_graph["nodes"]
        if node.get("id") in expected
    ]
    assert all(
        provider_id not in expected
        for provider_ids in app_graph["moduleComposition"].values()
        for provider_id in provider_ids
    )
    details = {detail["id"]: detail for detail in bundle["functionDetails"]}
    assert details["fn:student_system.app.main.main"]["executionRole"] == "entry"
    assert details["fn:student_system.app.main.client"]["executionRole"] == "orchestrator"
    assert details["fn:student_system.app.main.server"]["functionSurface"] == "execution"
    assert details["fn:student_system.app.main.client"]["source"]["text"]
    flow = bundle["projectGraph"]["executionFlows"][0]
    assert {
        "server(sockets)", "client(sockets)"
    } <= {node["label"] for node in flow["nodes"]}
    assert not [
        issue for issue in validate_bundle(bundle) if issue["severity"] == "error"
    ]


def test_execution_only_class_method_keeps_class_provider(tmp_path: Path) -> None:
    """A flow-only method is removed from APIs while its owner class remains."""

    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''def main() -> int:
    """Run the application flow."""
    return Runner().run()


class Runner:
    """Provide the application runner."""

    def run(self) -> int:
        """Run one execution flow."""
        return self.assist()

    def assist(self) -> int:
        """Return one step result."""
        return 1
''',
        encoding="utf-8",
    )
    config = {
        "projectName": "execution_only_method",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "executionEntrypoints": ["app.main:Runner.run"],
        "modules": [
            {
                "id": "app",
                "name": "应用",
                "include": ["app/*.py"],
                "role": "service",
                "executionOnlyCallables": ["app.main:Runner.run"],
            }
        ],
    }
    config_path = project / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    bundle = build_architecture(project, config_path)
    graph = bundle["moduleGraphs"][0]
    runner = next(node for node in graph["nodes"] if node["id"] == "cls:app.main.Runner")
    api_displays = {api["display"] for api in runner["providedApis"]}
    assert "Runner.run()" not in api_displays
    assert "Runner.assist()" in api_displays
    assert "fn:app.main.Runner.run" in graph["executionOnlyFunctionIds"]
    assert graph["capabilitySurface"]["hasProviders"] is True
    detail = next(
        item for item in bundle["functionDetails"]
        if item["id"] == "fn:app.main.Runner.run"
    )
    assert detail["isExecutionOnly"] is True
    assert detail["executionRole"] == "entry"
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_unresolved_execution_only_callable_is_an_error(tmp_path: Path) -> None:
    """Unknown execution-only declarations surface as validation errors."""

    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
    config = {
        "projectName": "bad_execution_only",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "modules": [
            {
                "id": "app",
                "name": "应用",
                "include": ["app/*.py"],
                "role": "service",
                "executionOnlyCallables": ["app.main:missing"],
            }
        ],
    }
    config_path = project / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    bundle = build_architecture(project, config_path)
    assert any(
        item["code"] == "EXECUTION_ONLY_CALLABLE_UNRESOLVED"
        for item in bundle["diagnostics"]
    )
    assert any(
        issue["code"] == "BUNDLE_ERROR_DIAGNOSTIC"
        for issue in validate_bundle(bundle)
    )
