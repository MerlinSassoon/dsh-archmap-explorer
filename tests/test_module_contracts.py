from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.render_manager import RenderManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate
render_html = RenderManager().render

ROOT = Path(__file__).parent / "fixtures" / "student_demo"
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"


def _module_graph(bundle: dict, module_id: str) -> dict:
    return next(graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == module_id)


def test_project_modules_have_roles_and_provided_api_counts() -> None:
    bundle = build_architecture(ROOT)
    modules = {module["id"]: module for module in bundle["projectGraph"]["modules"]}
    assert modules["entry"]["role"] == "service"
    assert modules["service"]["role"] == "service"
    assert modules["repo"]["role"] == "service"
    assert modules["entry"]["providedApiCount"] == 1
    for module in modules.values():
        graph = _module_graph(bundle, module["id"])
        assert module["providedApiCount"] == len(graph["providedApis"])
        assert graph["role"] == module["role"]


def test_provided_apis_are_derived_from_existing_function_facts() -> None:
    bundle = build_architecture(ROOT)
    detail_ids = {detail["id"] for detail in bundle["functionDetails"]}
    graph = _module_graph(bundle, "entry")
    main_api = next(api for api in graph["providedApis"] if api["functionId"] == "fn:app.main.main")
    assert main_api["kind"] == "function"
    assert main_api["providerKind"] == "function"
    assert main_api["isEntry"] is True
    assert main_api["providerId"] == "fn:app.main.main"
    for module_graph in bundle["moduleGraphs"]:
        for api in module_graph["providedApis"]:
            if api["functionId"]:
                assert api["functionId"] in detail_ids
            for evidence_id in api["evidenceFunctionIds"]:
                assert evidence_id in detail_ids


def test_class_contracts_include_abstract_methods_but_not_private_internals() -> None:
    bundle = build_architecture(CLASS_ROOT)
    graph = _module_graph(bundle, "worker")
    entries = {(api["providerName"], api["display"], api["kind"]) for api in graph["providedApis"]}
    assert ("Worker", "Worker.run()", "method") in entries
    assert ("Worker", "Worker.label()", "method") in entries
    assert ("EchoWorker", "EchoWorker.run()", "method") in entries
    assert ("make_worker", "make_worker()", "function") in entries
    assert not any("__init__" in display or "_helper" in display for _, display, _ in entries)


def test_project_layout_is_a_capability_board_without_dependency_edges() -> None:
    bundle = build_architecture(ROOT)
    project = bundle["projectGraph"]
    assert project["layout"]["mode"] == "module-cards"
    assert project["layout"]["edges"] == {}
    assert project["edges"] == []
    layout_ids = set(project["layout"]["nodes"])
    flow_card_ids = {card["id"] for card in project["flowCards"]}
    assert layout_ids == {module["id"] for module in project["modules"]} | flow_card_ids
    for node_id in layout_ids:
        assert project["layout"]["nodes"][node_id]["w"] > 0


def test_render_exposes_module_capability_contracts() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "module-contracts" not in html
    assert "renderModuleContracts" not in html
    assert "模块组成" in html
    assert "用户交互面 · " in html
    assert "类型关系" in html
    assert "module-api-chip" in html
    assert "providedApis" in html


def test_validator_detects_broken_provided_api() -> None:
    bundle = build_architecture(ROOT)
    graph = _module_graph(bundle, "service")
    graph["providedApis"][0]["functionId"] = "fn:missing.api"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "PROVIDED_API_FUNCTION_MISSING" for issue in issues)


def test_empty_capability_modules_do_not_create_project_grid_holes() -> None:
    """Visible project cards occupy the compact grid before hidden empty modules."""

    repo_root = Path(__file__).parent.parent
    bundle = build_architecture(
        repo_root / "examples" / "student_system",
        repo_root / "examples" / "student_system" / "archmap.config.json",
    )
    project = bundle["projectGraph"]
    layout = project["layout"]
    visible_modules = {
        module["id"]
        for module in project["modules"]
        if (module.get("capabilitySurface") or {}).get("hasProviders")
    }
    flow_card_ids = {card["id"] for card in project["flowCards"]}
    visible_ids = visible_modules | flow_card_ids
    hidden_ids = {
        module["id"]
        for module in project["modules"]
        if not (module.get("capabilitySurface") or {}).get("hasProviders")
    }
    ordered_ids = [
        node_id
        for node_id, _position in sorted(
            layout["nodes"].items(),
            key=lambda item: (item[1]["y"], item[1]["x"]),
        )
    ]
    assert hidden_ids
    assert set(ordered_ids[: len(visible_ids)]) == visible_ids
    assert set(ordered_ids[len(visible_ids):]) == hidden_ids
    assert layout["visibleCount"] == len(visible_ids)
    assert layout["columns"] == 3


def test_module_note_falls_back_to_docstring_and_records_source(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "main.py").write_text(
        '''"""应用模块说明。\n\n这一行不进入模块 note。\n"""\n\n\ndef main() -> None:\n    """Program entry."""\n    return None\n''',
        encoding="utf-8",
    )
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(
        '''{
  "projectName": "note_demo",
  "include": ["app/**/*.py"],
  "entrypoints": ["app.main:main"],
  "modules": [
    {"id": "app", "include": ["app/**/*.py"], "role": "service"}
  ]
}''',
        encoding="utf-8",
    )
    bundle = build_architecture(tmp_path, config_path)
    module = next(item for item in bundle["projectGraph"]["modules"] if item["id"] == "app")
    graph = _module_graph(bundle, "app")
    assert module["note"] == "应用模块说明。"
    assert module["noteSource"] == "docstring"
    assert graph["note"] == "应用模块说明。"
    assert graph["noteSource"] == "docstring"

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["modules"][0]["note"] = "配置覆盖说明。"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    overridden = build_architecture(tmp_path, config_path)
    module = next(item for item in overridden["projectGraph"]["modules"] if item["id"] == "app")
    assert module["note"] == "配置覆盖说明。"
    assert module["noteSource"] == "config"
