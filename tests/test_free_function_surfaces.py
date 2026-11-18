from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate


def _write_project(tmp_path: Path, config: dict) -> Path:
    """Write a small module with one class Provider and two free functions."""

    app = tmp_path / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''class Parser:
    """Parse terminal input."""

    def parse(self, value: str) -> str:
        """Parse one value."""
        return value.strip()


def parse_input(value: str) -> str:
    """Format and normalize one input value."""
    return value.strip().lower()


def main() -> str:
    """Run the entry flow."""
    return Parser().parse(parse_input(" VALUE "))
''',
        encoding="utf-8",
    )
    config.setdefault("projectName", "free_function_surface_demo")
    config.setdefault("include", ["app/*.py"])
    config.setdefault("entrypoints", ["app.main:main"])
    config.setdefault(
        "modules",
        [{"id": "app", "name": "应用", "include": ["app/*.py"], "role": "service"}],
    )
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def _free_details(bundle: dict) -> dict[str, dict]:
    return {
        detail["id"]: detail
        for detail in bundle["functionDetails"]
        if detail.get("ownerClassId") is None
    }


def test_auto_surface_keeps_unmarked_free_functions_internal(tmp_path: Path) -> None:
    """Auto mode must not promote public-named helpers just because they are importable."""

    config_path = _write_project(tmp_path, {})
    bundle = build_architecture(tmp_path, config_path)
    graph = bundle["moduleGraphs"][0]
    details = _free_details(bundle)
    parse_input = details["fn:app.main.parse_input"]
    main = details["fn:app.main.main"]
    assert parse_input["functionSurface"] == "internal"
    assert parse_input["functionSurfaceSource"] == "structure"
    assert "providerRole" not in parse_input
    assert main["functionSurface"] == "internal"
    assert not [
        api for api in graph["providedApis"]
        if api.get("functionId") in {"fn:app.main.parse_input", "fn:app.main.main"}
    ]
    assert graph["freeFunctionSurfaceCounts"] == {
        "capability": 0,
        "internal": 2,
        "execution": 0,
    }
    assert graph["capabilitySurface"]["hasProviders"] is True
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_module_default_capability_promotes_public_free_functions(tmp_path: Path) -> None:
    """An explicit capability default is the concise opt-in for function APIs."""

    config_path = _write_project(
        tmp_path,
        {
            "modules": [
                {
                    "id": "app",
                    "name": "应用",
                    "include": ["app/*.py"],
                    "role": "service",
                    "defaultFreeFunctionSurface": "capability",
                }
            ]
        },
    )
    bundle = build_architecture(tmp_path, config_path)
    graph = bundle["moduleGraphs"][0]
    parse_input = _free_details(bundle)["fn:app.main.parse_input"]
    assert parse_input["functionSurface"] == "capability"
    assert parse_input["functionSurfaceSource"] == "module_default"
    assert parse_input["providerRole"] == "manager"
    assert parse_input["roleSource"] == "surface"
    api_displays = {api["display"] for api in graph["providedApis"]}
    assert "parse_input(value: str)" in api_displays
    assert graph["freeFunctionSurfaceCounts"]["capability"] == 2


def test_explicit_public_exposure_overrides_internal_default(tmp_path: Path) -> None:
    """A callable-level public API declaration beats an internal module default."""

    config_path = _write_project(
        tmp_path,
        {
            "modules": [
                {
                    "id": "app",
                    "name": "应用",
                    "include": ["app/*.py"],
                    "role": "service",
                    "defaultFreeFunctionSurface": "internal",
                }
            ],
            "contract": {
                "apiExposure": {
                    "app.main.parse_input": "public",
                }
            },
        },
    )
    bundle = build_architecture(tmp_path, config_path)
    parse_input = _free_details(bundle)["fn:app.main.parse_input"]
    main = _free_details(bundle)["fn:app.main.main"]
    assert parse_input["functionSurface"] == "capability"
    assert parse_input["functionSurfaceSource"] == "exposure"
    assert parse_input["providerRole"] == "manager"
    assert main["functionSurface"] == "internal"


def test_execution_only_takes_precedence_over_capability_default(tmp_path: Path) -> None:
    """Execution-only declarations remain stricter than a capability default."""

    config_path = _write_project(
        tmp_path,
        {
            "modules": [
                {
                    "id": "app",
                    "name": "应用",
                    "include": ["app/*.py"],
                    "role": "service",
                    "defaultFreeFunctionSurface": "capability",
                    "executionOnlyCallables": ["app.main:main"],
                }
            ]
        },
    )
    bundle = build_architecture(tmp_path, config_path)
    graph = bundle["moduleGraphs"][0]
    main = _free_details(bundle)["fn:app.main.main"]
    assert main["functionSurface"] == "execution"
    assert main["executionRole"] == "entry"
    assert "providerRole" not in main
    assert main["id"] in graph["executionFreeFunctionIds"]
    assert graph["freeFunctionSurfaceCounts"]["execution"] == 1


def test_invalid_default_free_function_surface_falls_back_to_auto(tmp_path: Path) -> None:
    """Invalid surface defaults are visible diagnostics and fall back safely."""

    config_path = _write_project(
        tmp_path,
        {
            "modules": [
                {
                    "id": "app",
                    "name": "应用",
                    "include": ["app/*.py"],
                    "role": "service",
                    "defaultFreeFunctionSurface": "public",
                }
            ]
        },
    )
    bundle = build_architecture(tmp_path, config_path)
    assert any(
        item["code"] == "DEFAULT_FREE_FUNCTION_SURFACE_INVALID"
        for item in bundle["diagnostics"]
    )
    assert bundle["moduleGraphs"][0]["defaultFreeFunctionSurface"] == "auto"


def test_cross_module_call_is_capability_evidence_in_auto_mode(tmp_path: Path) -> None:
    """A helper consumed by another module is treated as an API boundary."""

    app = tmp_path / "app"
    tool = tmp_path / "tool"
    app.mkdir(parents=True)
    tool.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (tool / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''from tool.tool import normalize


def main() -> str:
    """Run the cross-module call."""
    return normalize(" Value ")
''',
        encoding="utf-8",
    )
    (tool / "tool.py").write_text(
        '''def normalize(value: str) -> str:
    """Normalize a cross-module value."""
    return value.strip().lower()
''',
        encoding="utf-8",
    )
    config = {
        "projectName": "cross_module_surface",
        "include": ["app/*.py", "tool/*.py"],
        "entrypoints": ["app.main:main"],
        "modules": [
            {"id": "app", "name": "应用", "include": ["app/*.py"], "role": "service"},
            {"id": "tool", "name": "工具", "include": ["tool/*.py"], "role": "service"},
        ],
    }
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    bundle = build_architecture(tmp_path, config_path)
    detail = next(
        item for item in bundle["functionDetails"]
        if item["id"] == "fn:tool.tool.normalize"
    )
    assert detail["functionSurface"] == "capability"
    assert detail["functionSurfaceSource"] == "call_graph"
    assert detail["providerRole"] == "manager"
