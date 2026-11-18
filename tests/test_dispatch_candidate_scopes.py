"""P11 dispatch candidate journey scope tests."""

from __future__ import annotations

import json
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager
from archmap.utility.config_utility import load_config

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

ROOT = Path(__file__).parent.parent


def _write_dispatch_project(
    tmp_path: Path,
    *,
    complete: bool = True,
    dispatch_config: dict | None = None,
) -> Path:
    """Create a minimal static-registry dispatch project and config."""

    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "main.py").write_text(
        '''def handler_a():\n    """Handle mode A."""\n    return "a"\n\n\ndef handler_b():\n    """Handle mode B."""\n    return "b"\n\n\ndef main(mode):\n    """Dispatch to a mode handler."""\n    handlers = {"a": handler_a, "b": handler_b}\n    return handlers[mode]()\n''',
        encoding="utf-8",
    )
    config = {
        "projectName": "dispatch_candidates_demo",
        "include": ["app/*.py"],
        "entrypoints": ["app.main:main"],
        "dispatchHints": [
            {
                "function": "app.main:main",
                "expression": "handlers[mode]",
                "candidates": ["app.main:handler_a", "app.main:handler_b"],
                "complete": complete,
                "reason": "config",
            }
        ],
        "modules": [
            {
                "id": "main",
                "name": "Main",
                "include": ["app/*.py"],
                "role": "service",
            }
        ],
    }
    if dispatch_config is not None:
        config["dispatchCandidates"] = dispatch_config
    config_path = project / "archmap.config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return config_path


def _execution_flow(bundle: dict) -> dict:
    """Return the single execution flow from a test bundle."""

    return bundle["projectGraph"]["executionFlows"][0]


def test_dispatch_candidate_journeys_are_opt_in(tmp_path: Path) -> None:
    """Dispatch nodes stay atomic when candidate journey config is absent."""

    config_path = _write_dispatch_project(tmp_path)
    bundle = build_architecture(tmp_path / "project", config_path)
    flow = _execution_flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert flow.get("dispatchGroups") == []
    assert "drilldown" not in dispatch
    assert bundle["stats"]["dispatchGroups"] == 0
    assert bundle["stats"]["dispatchCandidateScopes"] == 0
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_dispatch_candidate_group_creates_one_scope_per_candidate(tmp_path: Path) -> None:
    """Complete dispatch candidates become independent depth-one journeys."""

    config_path = _write_dispatch_project(
        tmp_path,
        dispatch_config={"enabled": True, "completeOnly": True},
    )
    bundle = build_architecture(tmp_path / "project", config_path)
    flow = _execution_flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    groups = flow["dispatchGroups"]
    assert len(groups) == 1
    group = groups[0]
    assert group["kind"] == "archmap.dispatch-group"
    assert group["parentNodeId"] == dispatch["id"]
    assert group["candidateSource"] == "config"
    assert group["candidateSetComplete"] is True
    assert group["candidateCount"] == 2
    assert group["candidateIds"] == [
        "fn:app.main.handler_a",
        "fn:app.main.handler_b",
    ]
    assert group["omittedCandidateIds"] == []
    assert len(group["scopes"]) == 2
    assert group["truncated"] is False

    assert dispatch["drilldown"]["kind"] == "dispatch"
    assert dispatch["drilldown"]["status"] == "available"
    assert dispatch["drilldown"]["dispatchGroupId"] == group["id"]
    assert dispatch["drilldown"]["candidateScopeCount"] == 2

    for scope in group["scopes"]:
        assert scope["kind"] == "archmap.execution-scope"
        assert scope["origin"] == "dispatch_candidate"
        assert scope["candidateSource"] == "config"
        assert scope["reason"] == "dispatch_candidate"
        assert scope["depth"] == 1
        assert scope["parentNodeId"] == dispatch["id"]
        assert scope["rootFunctionId"] in group["candidateIds"]
        assert not scope.get("scopes")
        assert not scope.get("dispatchGroups")
        assert scope["nodeCount"] > 0

    # Candidate journeys are independent views and never become control edges.
    candidate_ids = set(group["candidateIds"])
    assert not any(
        str(edge.get("from") or "") in candidate_ids
        or str(edge.get("to") or "") in candidate_ids
        for edge in flow["edges"]
    )
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_dispatch_candidate_complete_only_skips_incomplete_sets(tmp_path: Path) -> None:
    """Incomplete candidate sets are blocked by default without inventing paths."""

    config_path = _write_dispatch_project(
        tmp_path,
        complete=False,
        dispatch_config={"enabled": True, "completeOnly": True},
    )
    bundle = build_architecture(tmp_path / "project", config_path)
    flow = _execution_flow(bundle)
    dispatch = next(node for node in flow["nodes"] if node["kind"] == "dispatch")
    assert flow["dispatchGroups"] == []
    assert dispatch["drilldown"]["kind"] == "dispatch"
    assert dispatch["drilldown"]["status"] == "blocked"
    assert dispatch["drilldown"]["reason"] == "candidate_set_incomplete"
    assert any(
        item["code"] == "DISPATCH_CANDIDATE_SET_INCOMPLETE"
        for item in bundle["diagnostics"]
    )
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_dispatch_candidate_budget_truncates_and_marks_group(tmp_path: Path) -> None:
    """Per-dispatch candidate budgets keep deterministic generated/omitted sets."""

    config_path = _write_dispatch_project(
        tmp_path,
        dispatch_config={
            "enabled": True,
            "completeOnly": True,
            "maxScopesPerDispatch": 1,
        },
    )
    bundle = build_architecture(tmp_path / "project", config_path)
    group = _execution_flow(bundle)["dispatchGroups"][0]
    assert len(group["scopes"]) == 1
    assert group["omittedCandidateIds"] == ["fn:app.main.handler_b"]
    assert group["truncated"] is True
    assert any(
        item["code"] in {
            "DISPATCH_CANDIDATE_DISPATCH_BUDGET",
            "DISPATCH_CANDIDATE_FLOW_BUDGET",
        }
        for item in group["diagnostics"]
    )
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_dispatch_candidate_config_clamps_invalid_limits(tmp_path: Path) -> None:
    """Invalid dispatch journey budgets fall back with explicit diagnostics."""

    config_path = _write_dispatch_project(
        tmp_path,
        dispatch_config={
            "enabled": True,
            "maxScopesPerDispatch": -1,
            "maxScopesPerFlow": "bad",
            "maxNodesPerScope": 999,
            "maxEdgesPerScope": 0,
        },
    )
    config = load_config(tmp_path / "project", config_path)
    assert config.dispatch_candidates.enabled is True
    assert config.dispatch_candidates.max_scopes_per_dispatch == 16
    assert config.dispatch_candidates.max_scopes_per_flow == 32
    assert config.dispatch_candidates.max_nodes_per_scope == 80
    assert config.dispatch_candidates.max_edges_per_scope == 32
    codes = {item["code"] for item in config.config_diagnostics}
    assert "DISPATCH_CANDIDATE_LIMIT_INVALID" in codes


def test_self_dispatch_candidate_journeys_keep_main_flow_bounded() -> None:
    """ArchMap's args.func router exposes nine journeys without changing L0."""

    config_path = ROOT / "examples" / "archmap_v3.archmap.json"
    bundle = build_architecture(ROOT, config_path)
    flow = next(
        item
        for item in bundle["projectGraph"]["executionFlows"]
        if item["entrypointId"] == "fn:archmap.entry.cli_entry.main"
    )
    assert len(flow["nodes"]) == 4
    assert len(flow["edges"]) == 3
    assert len(flow["dispatchGroups"]) == 1
    group = flow["dispatchGroups"][0]
    assert group["candidateCount"] == 9
    assert len(group["scopes"]) == 9
    assert bundle["stats"]["dispatchGroups"] == 1
    assert bundle["stats"]["dispatchCandidateScopes"] == 9
    build_scope = next(
        scope
        for scope in group["scopes"]
        if scope["rootFunctionId"] == "fn:archmap.utility.cli_utility.cmd_build"
    )
    assert build_scope["nodeCount"] > 1
    assert not build_scope.get("dispatchGroups")
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_validator_rejects_broken_dispatch_group_links(tmp_path: Path) -> None:
    """Dispatch group parent, origin and root links are hard invariants."""

    config_path = _write_dispatch_project(
        tmp_path,
        dispatch_config={"enabled": True, "completeOnly": True},
    )
    bundle = build_architecture(tmp_path / "project", config_path)
    flow = _execution_flow(bundle)
    group = flow["dispatchGroups"][0]
    group["parentNodeId"] = "missing-dispatch"
    group["scopes"][0]["origin"] = "interface"
    group["scopes"][0]["depth"] = 2
    issues = validate_bundle(bundle)
    codes = {issue["code"] for issue in issues}
    assert "EXEC_DISPATCH_GROUP_PARENT" in codes
    assert "EXEC_DISPATCH_SCOPE_ORIGIN" in codes
    assert "EXEC_DISPATCH_SCOPE_DEPTH" in codes


def test_dispatch_candidate_bundle_matches_schema_6_4(tmp_path: Path) -> None:
    """Activated dispatch journeys satisfy the published schema 6.4."""

    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    config_path = _write_dispatch_project(
        tmp_path,
        dispatch_config={"enabled": True, "completeOnly": True},
    )
    bundle = build_architecture(tmp_path / "project", config_path)
    schema = json.loads(
        (ROOT / "docs" / "schema" / "archmap-v6.4-bundle.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(bundle, schema)
