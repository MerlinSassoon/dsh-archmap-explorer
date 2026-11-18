from __future__ import annotations

from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager

build_architecture = PipelineManager().build_architecture
validate_bundle = ValidationManager().validate

REPO_ROOT = Path(__file__).parent.parent


def test_self_build_validates_without_expression_flow_graph() -> None:
    bundle = build_architecture(REPO_ROOT / "archmap")
    issues = validate_bundle(bundle)
    assert not [issue for issue in issues if issue["severity"] == "error"]
    assert bundle["functionDetails"]
    assert bundle["callSites"]
    assert "functionFlows" not in bundle


def test_nested_calls_in_conditions_are_collected() -> None:
    repo_root = Path(__file__).parent.parent
    bundle = build_architecture(repo_root / "tests" / "fixtures" / "class_demo")
    run = next(detail for detail in bundle["functionDetails"] if detail["name"] == "run")
    assert run["calleeCount"] >= 1
    assert any(site["fromFunctionId"] == run["id"] for site in bundle["callSites"])


def test_context_manager_calls_are_annotated_without_marking_plain_instantiation() -> None:
    config = REPO_ROOT / "examples" / "student_system.archmap.json"
    bundle = build_architecture(REPO_ROOT / "Projects" / "student_system", config)
    spinner_call = next(
        site for site in bundle["callSites"]
        if site["fromFunctionId"] == "fn:student_system.app.main.server"
        and site["toFunctionId"] == "fn:student_system.async_feedback.spinner_manager.Spinner.__init__"
    )
    assert spinner_call["kind"] == "instantiate"
    assert spinner_call["usageKind"] == "context_manager"

    menu_call = next(
        site for site in bundle["callSites"]
        if site["fromFunctionId"] == "fn:student_system.app.main.client"
        and site["toFunctionId"] == "fn:student_system.menu.menu_manager.MenuSystem.__init__"
    )
    assert menu_call["kind"] == "instantiate"
    assert menu_call["usageKind"] == "instantiate"
