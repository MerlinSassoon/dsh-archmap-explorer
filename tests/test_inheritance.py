from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "inheritance_demo"
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"


def _bundle() -> dict:
    return build_architecture(ROOT)


def _graph(bundle: dict, module_id: str) -> dict:
    return next(graph for graph in bundle["moduleGraphs"] if graph["moduleId"] == module_id)


def _class(graph: dict, name: str) -> dict:
    return next(node for node in graph["nodes"] if node["kind"] == "class" and node["name"] == name)


def _detail(bundle: dict, qualified_name: str) -> dict:
    return next(detail for detail in bundle["functionDetails"] if detail["qualifiedName"].endswith(qualified_name))


def test_inherits_and_implements_are_resolved_structural_edges() -> None:
    bundle = _bundle()
    relations = {
        (relation["fromClassId"], relation["kind"], relation["toClassId"])
        for relation in bundle["projectGraph"]["typeRelations"]
    }
    assert (
        "cls:app.impl.EchoWorker",
        "implements",
        "cls:app.base.Worker",
    ) in relations
    assert (
        "cls:app.impl.EmailNotifier",
        "implements",
        "cls:app.base.Notifier",
    ) in relations
    module_relations = {
        (relation["fromClassId"], relation["kind"], relation["toClassId"])
        for graph in bundle["moduleGraphs"]
        for relation in graph["typeRelations"]
    }
    assert module_relations == relations
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_class_nodes_carry_hierarchy_and_abstractness() -> None:
    bundle = _bundle()
    impl = _graph(bundle, "impl")
    echo = _class(impl, "EchoWorker")
    silent = _class(impl, "SilentWorker")
    assert echo["baseClassIds"] == ["cls:app.base.Worker"]
    assert echo["isAbstract"] is False
    assert echo["classKind"] == "service"
    assert "fn:app.impl.EchoWorker.run" in echo["publicMethodIds"]
    assert silent["isAbstract"] is True
    assert silent["classKind"] == "abstract"
    assert silent["abstractMethodNames"] == ["run"]
    worker = _class(_graph(bundle, "base"), "Worker")
    assert set(worker["subclassIds"]) == {
        "cls:app.impl.EchoWorker",
        "cls:app.impl.LoudWorker",
        "cls:app.impl.SilentWorker",
    }


def test_inherited_capabilities_preserve_declaration_and_override_origin() -> None:
    bundle = _bundle()
    impl = _graph(bundle, "impl")
    echo = _class(impl, "EchoWorker")
    apis = {api["display"]: api for api in echo["providedApis"]}
    label = apis["EchoWorker.label()"]
    assert label["inherited"] is True
    assert label["declaredInProviderId"] == "cls:app.base.Worker"
    assert label["inheritedFromProviderId"] == "cls:app.base.Worker"
    assert label["providerId"] == "cls:app.impl.EchoWorker"
    assert "fn:app.base.Worker.label" in label["evidenceFunctionIds"]
    run = apis["EchoWorker.run()"]
    assert run["inherited"] is False
    assert run["overridesCapabilityId"] == "api:fn:app.base.Worker.run"
    assert echo["declaredApiCount"] + echo["inheritedApiCount"] == echo["providedApiCount"]
    provider = next(item for item in impl["apiProviders"] if item["providerName"] == "EchoWorker")
    assert provider["inheritedApiCount"] >= 1
    assert provider["declaredApiCount"] >= 1


def test_abstract_contract_calls_become_polymorphic_candidates() -> None:
    bundle = _bundle()
    sites = {site["calleeText"]: site for site in bundle["callSites"]}
    worker_call = sites["worker.run"]
    assert worker_call["polymorphic"] is True
    assert worker_call["dispatchKind"] == "polymorphic"
    assert worker_call["resolved"] is False
    assert worker_call["toFunctionId"] is None
    assert worker_call["candidates"] == [
        "fn:app.impl.EchoWorker.run",
        "fn:app.impl.LoudWorker.run",
    ]
    notify_call = sites["notifier.notify"]
    assert notify_call["polymorphic"] is True
    assert notify_call["candidates"] == ["fn:app.impl.EmailNotifier.notify"]
    # Concrete inherited calls still resolve statically to the declared base function.
    label_call = sites["self.label"]
    assert label_call["resolved"] is True
    assert label_call["polymorphic"] is False
    assert label_call["toFunctionId"] == "fn:app.base.Worker.label"


def test_function_details_expose_override_and_polymorphic_neighborhood() -> None:
    bundle = _bundle()
    run = _detail(bundle, "EchoWorker.run")
    base_run = _detail(bundle, "Worker.run")
    assert run["overrideOfFunctionId"] == "fn:app.base.Worker.run"
    assert "fn:app.impl.EchoWorker.run" in base_run["overriddenByFunctionIds"]
    assert run["polymorphicCallerCount"] >= 1
    assert run["polymorphicCallers"][0]["polymorphic"] is True
    assert run["polymorphicCallers"][0]["functionId"] == "fn:app.main.execute"


def test_polymorphic_dispatch_candidates_reach_execution_flow(tmp_path: Path) -> None:
    config = json.loads((ROOT / "archmap.config.json").read_text(encoding="utf-8"))
    config["executionEntrypoints"] = ["app.main:execute"]
    config.pop("mainModule", None)
    for module in config["modules"]:
        module.pop("kind", None)
        if module["role"] == "main":
            module["role"] = "entry"
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    bundle = build_architecture(ROOT, config_path)
    flow = next(
        flow for flow in bundle["projectGraph"]["executionFlows"]
        if flow["entrypointId"] == "fn:app.main.execute"
    )
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert dispatch["candidateSource"] == "polymorphic"
    assert dispatch["candidateCount"] == 2
    assert dispatch["candidateSetComplete"] is False
    assert all(edge["kind"] != "composition" for edge in flow["edges"])


def test_class_demo_inherits_concrete_method_and_resolves_inherited_constructor() -> None:
    bundle = build_architecture(CLASS_ROOT)
    graph = bundle["moduleGraphs"][0]
    echo = next(node for node in graph["nodes"] if node["name"] == "EchoWorker")
    label = next(api for api in echo["providedApis"] if api["display"] == "EchoWorker.label()")
    assert label["inherited"] is True
    constructor_sites = [site for site in bundle["callSites"] if site["kind"] == "instantiate"]
    assert constructor_sites
    assert all(site["resolved"] for site in constructor_sites)
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_validator_rejects_broken_type_relation_and_resolved_polymorphic_call() -> None:
    bundle = _bundle()
    bundle["projectGraph"]["typeRelations"][0]["toClassId"] = "cls:missing.Base"
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "TYPE_RELATION_ENDPOINT" for issue in issues)

    bundle = _bundle()
    site = next(site for site in bundle["callSites"] if site["polymorphic"])
    site["resolved"] = True
    site["toFunctionId"] = site["candidates"][0]
    issues = validate_bundle(bundle)
    assert any(issue["code"] == "POLYMORPHIC_CALL_RESOLVED" for issue in issues)


def test_relative_module_import_and_generic_protocol_are_resolved(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "base.py").write_text(
        "from typing import Protocol, TypeVar\nT = TypeVar('T')\n\nclass Base:\n    def ping(self):\n        return 'pong'\n\nclass Store(Protocol[T]):\n    def get(self, key: str) -> T:\n        ...\n",
        encoding="utf-8",
    )
    (app / "sub.py").write_text(
        "from . import base\n\nclass Child(base.Base):\n    pass\n",
        encoding="utf-8",
    )
    (app / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    config = {
        "projectName": "relative_types",
        "language": "python",
        "include": ["app/*.py"],
        "mainModule": "main",
        "entrypoints": ["app.main:main"],
        "modules": [
            {"id": "main", "name": "主流程", "kind": "main", "include": ["app/main.py"], "role": "main"},
            {"id": "types", "name": "类型", "kind": "functional", "include": ["app/base.py", "app/sub.py"], "role": "service"},
        ],
    }
    config_path = tmp_path / "archmap.config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    bundle = build_architecture(tmp_path, config_path)
    graph = next(item for item in bundle["moduleGraphs"] if item["moduleId"] == "types")
    child = _class(graph, "Child")
    store = _class(graph, "Store")
    assert child["baseClassIds"] == ["cls:app.base.Base"]
    assert store["classKind"] == "interface"
    assert store["isAbstract"] is True
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]
