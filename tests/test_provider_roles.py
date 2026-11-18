from __future__ import annotations

import json
from pathlib import Path

import pytest

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent / "fixtures" / "roles_demo"


def _roles_bundle():
    return build_architecture(ROOT)


def test_provider_roles_and_module_composition() -> None:
    bundle = _roles_bundle()
    graph = bundle["moduleGraphs"][0]
    nodes = {node["id"]: node for node in graph["nodes"]}

    expected = {
        "cls:app.roles.AppConfig": ("config", "structure"),
        "cls:app.roles.Order": ("model", "structure"),
        "cls:app.roles.OrderManager": ("manager", "structure"),
        "cls:app.roles.OrderRepository": ("adapter", "structure"),
        "cls:app.roles.Worker": ("contract", "structure"),
        "cls:app.roles.Spinner": ("component", "structure"),
        "cls:app.roles.DecoratedWidget": ("component", "decorator"),
        "cls:app.roles.ConfigOverrideThing": ("model", "config"),
        "fn:app.roles.helper": ("utility", "structure"),
        "fn:app.roles.main": ("entry", "entrypoint"),
    }
    for provider_id, (role, source) in expected.items():
        assert nodes[provider_id]["providerRole"] == role
        assert nodes[provider_id]["roleSource"] == source

    composition = graph["moduleComposition"]
    assert composition["config"] == ["cls:app.roles.AppConfig"]
    assert composition["model"] == [
        "cls:app.roles.ConfigOverrideThing",
        "cls:app.roles.Order",
    ]
    assert composition["adapter"] == ["cls:app.roles.OrderRepository"]
    assert composition["contract"] == ["cls:app.roles.Worker"]
    assert "fn:app.roles.main" in composition["entry"]
    assert graph["providerRoleCounts"]["component"] == 2
    assert graph["publicProviderRoleCounts"]["utility"] == 0
    assert graph["providerRoleCounts"]["utility"] == 2
    assert graph["publicModuleComposition"]["utility"] == []
    assert bundle["projectGraph"]["modules"][0]["providerRoleCounts"] == graph["providerRoleCounts"]
    assert bundle["projectGraph"]["modules"][0]["publicProviderRoleCounts"] == graph["publicProviderRoleCounts"]


def test_config_and_model_are_type_cards_not_module_apis() -> None:
    bundle = _roles_bundle()
    graph = bundle["moduleGraphs"][0]
    nodes = {node["id"]: node for node in graph["nodes"]}
    api_provider_ids = {provider["providerId"] for provider in graph["apiProviders"]}
    api_ids = {api["id"] for api in graph["providedApis"]}

    assert "cls:app.roles.AppConfig" not in api_provider_ids
    assert "cls:app.roles.Order" not in api_provider_ids
    assert "cls:app.roles.ConfigOverrideThing" not in api_provider_ids
    assert not any("AppConfig.as_dict" in api_id for api_id in api_ids)
    assert not any("Order.as_dict" in api_id for api_id in api_ids)
    assert not any("ConfigOverrideThing.dump" in api_id for api_id in api_ids)

    app_config = nodes["cls:app.roles.AppConfig"]
    assert app_config["providedApis"] == []
    assert app_config["typeSummary"]["fieldCount"] == 3
    assert [field["name"] for field in app_config["typeSummary"]["fields"]] == [
        "host",
        "port",
        "debug",
    ]
    assert app_config["typeSummary"]["fields"][0]["default"] == "'localhost'"

    order = nodes["cls:app.roles.Order"]
    assert order["providedApis"] == []
    assert order["typeSummary"]["fieldCount"] == 2

    provider_roles = {provider["providerId"]: provider["providerRole"] for provider in graph["apiProviders"]}
    assert provider_roles["cls:app.roles.OrderManager"] == "manager"
    assert provider_roles["cls:app.roles.OrderRepository"] == "adapter"
    assert provider_roles["cls:app.roles.Spinner"] == "component"
    assert provider_roles["cls:app.roles.Worker"] == "contract"
    assert provider_roles["fn:app.roles.main"] == "entry"
    assert "fn:app.roles.helper" not in provider_roles
    assert nodes["fn:app.roles.helper"]["providerRole"] == "utility"
    assert nodes["fn:app.roles.helper"]["providerVisibility"] == "internal"
    assert nodes["fn:app.roles.helper"]["ownerProviderId"] == "fn:app.roles.main"
    assert nodes["fn:app.roles._provider_role"]["providerVisibility"] == "internal"
    assert nodes["fn:app.roles._provider_role"]["providedApis"] == []


def test_protocol_capability_carries_provider_role_and_entry_detail_role() -> None:
    bundle = _roles_bundle()
    graph = bundle["moduleGraphs"][0]
    spinner_api = next(
        api for api in graph["providedApis"] if api["providerId"] == "cls:app.roles.Spinner"
    )
    assert spinner_api["kind"] == "context_manager"
    assert spinner_api["providerRole"] == "component"
    assert spinner_api["roleSource"] == "structure"

    main_detail = next(detail for detail in bundle["functionDetails"] if detail["id"] == "fn:app.roles.main")
    assert main_detail["providerRole"] == "entry"
    assert main_detail["roleSource"] == "entrypoint"
    assert main_detail["isEntry"] is True
    assert bundle["stats"]["providerRoles"]["entry"] == 1


def test_validator_rejects_config_model_api_leak_and_composition_drift() -> None:
    bundle = _roles_bundle()
    graph = bundle["moduleGraphs"][0]
    app_config = next(node for node in graph["nodes"] if node["id"] == "cls:app.roles.AppConfig")
    app_config["providedApis"] = [graph["providedApis"][0]]
    graph["providerRoleCounts"]["config"] = 0

    issues = validate_bundle(bundle)
    codes = {issue["code"] for issue in issues}
    assert "ROLE_API_LEAK" in codes
    assert "MODULE_COMPOSITION_ROLE_MISMATCH" in codes or "PROVIDER_ROLE_COUNT" in codes


def test_archmap_self_roles_remove_config_model_api_noise() -> None:
    repo_root = Path(__file__).parent.parent
    bundle = build_architecture(repo_root, repo_root / "examples" / "archmap_v3.archmap.json")
    nodes = {
        node["id"]: node
        for graph in bundle["moduleGraphs"]
        for node in graph["nodes"]
        if node.get("kind") in {"class", "function"}
    }
    assert nodes["cls:archmap.config.project_config.ProjectConfig"]["providerRole"] == "config"
    assert nodes["cls:archmap.config.project_config.ModuleConfig"]["providerRole"] == "config"
    assert nodes["cls:archmap.model.analysis_model.FunctionInfo"]["providerRole"] == "model"
    assert nodes["cls:archmap.model.contract_model.ApiCapability"]["providerRole"] == "model"
    assert nodes["cls:archmap.frontends.python.call_utility.CallResolver"]["providerRole"] == "utility"
    assert nodes["cls:archmap.frontends.python.python_manager.PythonFrontend"]["providerRole"] == "manager"
    assert nodes["cls:archmap.model.frontend_contract.LanguageFrontend"]["providerRole"] == "contract"
    assert nodes["fn:archmap.frontends.python.analysis_utility.analyze_project"]["providerRole"] == "utility"
    assert nodes["fn:archmap.frontends.python.analysis_utility.analyze_project"]["providerVisibility"] == "internal"
    assert nodes["fn:archmap.frontends.python.analysis_utility.analyze_project"]["ownerProviderId"] == "cls:archmap.frontends.python.python_manager.PythonFrontend"
    assert nodes["fn:archmap.frontends.python.analysis_utility.analyze_project"]["providedApiCount"] == 0
    assert nodes["fn:archmap.frontends.python.call_utility.collect_call_sites"]["providerRole"] == "utility"
    assert nodes["fn:archmap.frontends.python.call_utility.collect_call_sites"]["ownerProviderId"] == "cls:archmap.frontends.python.python_manager.PythonFrontend"
    assert nodes["fn:archmap.utility.call_utility._calls_in_function"]["providerRole"] == "utility"
    assert nodes["fn:archmap.utility.call_utility._calls_in_function"]["providerVisibility"] == "internal"
    assert nodes["fn:archmap.utility.graph_utility._aggregate_relations"]["providerRole"] == "utility"
    assert nodes["cls:archmap.config.project_config.ProjectConfig"]["providedApis"] == []
    assert nodes["cls:archmap.config.project_config.ProjectConfig"]["typeSummary"]["fieldCount"] > 0

    displays = [
        api["display"]
        for graph in bundle["moduleGraphs"]
        for api in graph["providedApis"]
    ]
    assert not any(display.startswith(("ApiCapability.as_dict", "ClassUsage.as_dict")) for display in displays)
    assert not any(display.startswith("ContractModel.capabilities_by_") for display in displays)
    assert not any(display.startswith("_CallVisitor.") for display in displays)


def test_roles_bundle_matches_current_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (Path(__file__).parent.parent / "docs" / "schema" / "archmap-v4-bundle.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(_roles_bundle(), schema)


def test_self_build_only_exposes_facade_managers_and_hides_internal_stages() -> None:
    repo_root = Path(__file__).parent.parent
    bundle = build_architecture(repo_root, repo_root / "examples" / "archmap_v3.archmap.json")
    public_managers = {
        (node["id"], node["name"])
        for graph in bundle["moduleGraphs"]
        for node in graph["nodes"]
        if node.get("kind") == "class" and node.get("providerRole") == "manager" and node.get("providerVisibility") == "public"
    }
    assert {name for _, name in public_managers} == {
        "PipelineManager",
        "FrontendManager",
        "PythonFrontend",
        "GraphManager",
        "RenderManager",
        "ValidationManager",
    }
    api_provider_ids = {
        provider["providerId"]
        for graph in bundle["moduleGraphs"]
        for provider in graph["apiProviders"]
    }
    assert "fn:archmap.frontends.python.analysis_utility.analyze_project" not in api_provider_ids
    assert "fn:archmap.frontends.python.call_utility.collect_call_sites" not in api_provider_ids
    assert "fn:archmap.utility.graph_utility.build_bundle" not in api_provider_ids
