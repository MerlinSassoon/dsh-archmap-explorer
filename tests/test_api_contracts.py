from __future__ import annotations

from pathlib import Path

from archmap.pipeline import build_architecture
from archmap.validate import validate_bundle

ROOT = Path(__file__).parent / "fixtures" / "contracts_demo"


def _bundle() -> dict:
    return build_architecture(ROOT)


def _graph(bundle: dict) -> dict:
    return bundle["moduleGraphs"][0]


def _class_node(graph: dict, name: str) -> dict:
    return next(node for node in graph["nodes"] if node["kind"] == "class" and node["name"] == name)


def test_context_manager_is_one_capability_not_magic_methods() -> None:
    graph = _graph(_bundle())
    resource = _class_node(graph, "Resource")
    kinds = {api["kind"] for api in resource["providedApis"]}
    displays = {api["display"] for api in resource["providedApis"]}
    assert "context_manager" in kinds
    assert "with Resource(name: str='default')" in displays
    assert "Resource.run()" in displays
    assert not any("__init__" in display or "__enter__" in display or "__exit__" in display for display in displays)
    assert resource["usage"]["protocols"] == ["context_manager"]
    assert resource["usage"]["constructor"]["signature"] == "Resource(name: str='default')"


def test_callable_and_iterable_protocols_are_synthesized() -> None:
    graph = _graph(_bundle())
    callable_node = _class_node(graph, "CallableThing")
    iterable_node = _class_node(graph, "IterableThing")
    assert {api["kind"] for api in callable_node["providedApis"]} == {"callable"}
    assert {api["kind"] for api in iterable_node["providedApis"]} == {"iterable"}


def test_sequence_protocols_are_intentionally_deferred() -> None:
    graph = _graph(_bundle())
    sequence = _class_node(graph, "SequenceThing")
    assert sequence["providedApis"] == []
    assert sequence["usage"]["protocols"] == []


def test_exposure_tags_underscore_entries_and_config_override() -> None:
    bundle = _bundle()
    graph = _graph(bundle)
    by_display = {api["display"]: api for api in graph["providedApis"]}
    assert by_display["Resource.run()"]["exposureSource"] == "docstring"
    assert by_display["Resource.comment_public()"]["exposureSource"] == "comment"
    assert by_display["main()"]["exposureSource"] == "entrypoint"
    assert by_display["main()"]["isEntry"] is True
    assert by_display["_config_public()"]["exposureSource"] == "config"
    assert "_local_helper()" not in by_display
    assert not any("_helper" in display for display in by_display)


def test_module_api_providers_group_capabilities_by_provider() -> None:
    graph = _graph(_bundle())
    providers = {provider["providerName"]: provider for provider in graph["apiProviders"]}
    assert set(providers) == {"Resource", "CallableThing", "IterableThing", "main", "_config_public"}
    assert providers["Resource"]["apiCount"] == 3
    flattened = {api["id"] for api in graph["providedApis"]}
    grouped = {api["id"] for provider in graph["apiProviders"] for api in provider["apis"]}
    assert flattened == grouped


def test_contract_bundle_validates_and_details_carry_exposure() -> None:
    bundle = _bundle()
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]
    detail = next(item for item in bundle["functionDetails"] if item["name"] == "run")
    assert detail["apiExposure"] == "public"
    assert detail["apiExposureSource"] == "docstring"
    entry = next(item for item in bundle["functionDetails"] if item["name"] == "main")
    assert entry["isEntry"] is True
