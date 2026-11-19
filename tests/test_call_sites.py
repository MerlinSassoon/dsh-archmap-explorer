from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.validate_manager import ValidationManager
from archmap.utility.query_utility import build_trace

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


def _write_project(root: Path, files: dict[str, str], config: dict | None = None) -> None:
    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (root / "archmap.config.json").write_text(
        json.dumps(
            config
            or {
                "projectName": "resolution_demo",
                "include": ["app/**/*.py"],
                "entrypoints": ["app.main:main"],
            }
        ),
        encoding="utf-8",
    )


def test_cast_attribute_chain_resolves_controller_method(tmp_path: Path) -> None:
    _write_project(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/main.py": """
from typing import cast


class Controller:
    def handle(self) -> int:
        return 1


class Server:
    def __init__(self, controller: Controller) -> None:
        self.controller = controller


class Handler:
    def __init__(self, server: Server) -> None:
        self.server = server

    def run(self) -> int:
        server = cast(Server, self.server)
        return server.controller.handle()


def main() -> int:
    return Handler(Server(Controller())).run()
""",
        },
    )
    bundle = build_architecture(tmp_path)
    site = next(
        item
        for item in bundle["callSites"]
        if item["calleeText"] == "server.controller.handle"
    )
    assert site["resolved"] is True
    assert site["toFunctionId"].endswith("Controller.handle")
    detail = next(
        item for item in bundle["functionDetails"] if item["id"].endswith("Controller.handle")
    )
    assert detail["callerCount"] == 1
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_protocol_single_implementation_resolves_candidates(tmp_path: Path) -> None:
    _write_project(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/main.py": """
from typing import Protocol


class Store(Protocol):
    def save(self, value: str) -> None: ...


class JsonStore(Store):
    def save(self, value: str) -> None:
        print(value)


class Manager:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(self, value: str) -> None:
        self.store.save(value)


def main() -> None:
    Manager(JsonStore()).run("x")
""",
        },
    )
    bundle = build_architecture(tmp_path)
    site = next(item for item in bundle["callSites"] if item["calleeText"] == "self.store.save")
    assert site["polymorphic"] is True
    assert site["candidates"] == ["fn:app.main.JsonStore.save"]
    impl = next(
        item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.JsonStore.save"
    )
    assert impl["polymorphicCallerCount"] == 1
    assert not [issue for issue in validate_bundle(bundle) if issue["severity"] == "error"]


def test_unresolved_protocol_is_warning_and_build_still_renders(tmp_path: Path) -> None:
    _write_project(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/main.py": """
from typing import Protocol


class Store(Protocol):
    def save(self, value: str) -> None: ...


class Manager:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(self, value: str) -> None:
        self.store.save(value)


def main() -> None:
    pass
""",
        },
    )
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "archmap", "build", str(tmp_path), "--out", str(out)],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "architecture.html").exists()
    check = subprocess.run(
        [sys.executable, "-m", "archmap", "check", str(out / "architecture.json"), "--json"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    payload = json.loads(check.stdout)
    assert payload["ok"] is True
    assert payload["errorCount"] == 0
    assert any(
        issue["code"] == "POLYMORPHIC_CALL_CANDIDATES"
        and issue["severity"] == "warning"
        for issue in payload["issues"]
    )


def test_unresolved_detail_and_trace_reference_same_call_site(tmp_path: Path) -> None:
    _write_project(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/main.py": """
class Repo:
    def save(self, value):
        print(value)


def main(repo):
    repo.save("x")
""",
        },
    )
    bundle = build_architecture(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"].endswith("Repo.save"))
    assert detail["callerCount"] == 0
    assert detail["unresolvedCallerCount"] == 1
    unresolved_id = detail["unresolvedCallers"][0]["callSiteId"]

    trace = build_trace(bundle, detail["id"], direction="inbound")
    assert trace["unresolvedCount"] == 1
    assert trace["unresolvedReferences"][0]["callSiteId"] == unresolved_id
