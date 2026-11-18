from __future__ import annotations

import json
import re
from pathlib import Path

from archmap.managers.pipeline_manager import PipelineManager
from archmap.managers.render_manager import RenderManager

build_architecture = PipelineManager().build_architecture
render_html = RenderManager().render

ROOT = Path(__file__).parent / "fixtures" / "student_demo"
CLASS_ROOT = Path(__file__).parent / "fixtures" / "class_demo"
CONTRACT_ROOT = Path(__file__).parent / "fixtures" / "contracts_demo"
ROLE_ROOT = Path(__file__).parent / "fixtures" / "roles_demo"


def test_render_is_self_contained_and_embeds_real_data() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "@import" not in html
    assert "window.__ARCHMAP_DATA__" in html
    assert "fn:app.main.main" in html
    assert "student_demo" in html
    assert len(html) > 50000


def test_render_includes_annotations() -> None:
    bundle = build_architecture(ROOT)
    annotations = {
        "version": 1,
        "nodes": {
            "fn:app.main.main": {
                "summary": "程序入口",
                "details": "加载并处理学生数据",
                "sourceHash": bundle["functionDetails"][0]["sourceHash"],
            }
        },
    }
    html = render_html(bundle, annotations)
    assert "程序入口" in html
    assert "加载并处理学生数据" in html


def test_render_does_not_rescan_injected_json_placeholders() -> None:
    bundle = build_architecture(ROOT)
    payload = "__APP_JS__ __CSS__ __TITLE__ __PROJECT_NAME__ __ARCHMAP_DATA_JSON__</script>\nnext"
    bundle["functionDetails"][0]["source"]["text"] = payload
    html = render_html(bundle)
    match = re.search(r"window\.__ARCHMAP_DATA__ = (.*?);\n</script>", html, re.S)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert embedded["functionDetails"][0]["source"]["text"] == payload
    assert "\\/script>" in match.group(1)


def test_render_contains_method_detail_contract() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "method-page" in html
    assert "method-source" in html
    assert "data-goto-method" in html
    assert "functionDetails" in html
    assert "functionFlows" not in html


def test_render_keeps_system_color_scheme_support() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "prefers-color-scheme: dark" in html
    assert "color-scheme: light dark" in html
    assert "--method-bg: #f8fafc" in html
    assert "--method-bg: #090d13" in html
    assert ".viewport.is-detail { cursor: default; background: var(--method-bg); }" in html
    assert "method-page" in html


def test_render_removed_module_inline_expand_feature() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert "data-expand" not in html
    assert "module-mini" not in html
    assert "renderModuleMini" not in html
    assert "data-open-module" in html


def test_render_contains_class_component_contract() -> None:
    bundle = build_architecture(CLASS_ROOT)
    html = render_html(bundle)
    assert "renderModuleClassNode" in html
    assert "class-method-row" in html
    assert "cls:app.worker.EchoWorker" in html
    assert "抽象类/接口是契约节点" in html


def test_render_contains_api_contract_capabilities() -> None:
    bundle = build_architecture(CONTRACT_ROOT)
    html = render_html(bundle)
    assert "apiProviders" in html
    assert "context_manager" in html
    assert "api-provider" in html
    assert "with Resource" in html
    match = re.search(r"window\.__ARCHMAP_DATA__ = (.*?);\n</script>", html, re.S)
    assert match is not None
    embedded = json.loads(match.group(1))
    displays = [
        api["display"]
        for graph in embedded["moduleGraphs"]
        for api in graph["providedApis"]
    ]
    assert any(display.startswith("with Resource") for display in displays)
    assert not any("__enter__" in display or "__exit__" in display or "__init__" in display for display in displays)


def test_render_separates_main_flow_from_module_capabilities() -> None:
    bundle = build_architecture(ROOT)
    html = render_html(bundle)
    assert 'id="projectFlowEntry"' not in html
    assert "data-open-flow-card" in html
    assert 'id="flowPicker"' in html
    assert "renderFlowPage" in html
    assert "Module capability" in html
    assert "main-flow-node" not in html
    assert "renderMainFlowPage" not in html
    assert "data-main-view" not in html
    assert "boundary-node" not in html
    assert "module-ports" not in html
    match = re.search(r"window\.__ARCHMAP_DATA__ = (.*?);\n</script>", html, re.S)
    assert match is not None
    embedded = json.loads(match.group(1))
    assert "mainModuleId" not in embedded["projectGraph"]
    assert "mainFlows" not in embedded["projectGraph"]
    assert embedded["projectGraph"]["executionFlows"]
    assert "boundaryNodes" not in embedded["projectGraph"]


def test_render_contains_provider_roles_and_type_cards() -> None:
    bundle = build_architecture(ROLE_ROOT)
    html = render_html(bundle)
    assert "providerRoleLabel" in html
    assert "roleCompositionBlock" in html
    assert "typeFieldChips" in html
    assert "type-field-list" in html
    assert "CLASS / MODEL" not in html
    assert "CONFIG" in html
    assert "MODEL" in html
    assert "AppConfig" in html
    match = re.search(r"window\.__ARCHMAP_DATA__ = (.*?);\n</script>", html, re.S)
    assert match is not None
    embedded = json.loads(match.group(1))
    graph = embedded["moduleGraphs"][0]
    assert graph["moduleComposition"]["config"] == ["cls:app.roles.AppConfig"]
    app_config = next(node for node in graph["nodes"] if node["id"] == "cls:app.roles.AppConfig")
    assert app_config["providerRole"] == "config"
    assert app_config["typeSummary"]["fieldCount"] == 3


def test_render_includes_context_manager_provider_semantics() -> None:
    repo_root = Path(__file__).parent.parent
    bundle = build_architecture(
        repo_root / "Projects" / "student_system",
        repo_root / "examples" / "student_system.archmap.json",
    )
    html = render_html(bundle)
    assert "with Spinner(message: str='加载中')" in html
    assert "context_manager" in html
    assert "usageKind" in html


def test_execution_edges_use_dashes_only_for_inferred_relations() -> None:
    html = render_html(build_architecture(ROOT))

    assert ".execution-edge.kind-default { stroke: #94a3b8; }" in html
    assert ".execution-edge.kind-break" not in html
    assert ".execution-edge.kind-continue" not in html
    assert ".execution-edge.kind-return" not in html
    assert ".graph-edge.kind-composition { stroke: #f59e0b; stroke-dasharray: 7 6;" in html
    assert ".graph-edge.kind-call_path { stroke: #7dd3fc; stroke-dasharray: 2 4;" in html


def test_execution_cards_show_notes_instead_of_signatures() -> None:
    html = render_html(build_architecture(ROOT))

    assert "exec-node-note" in html
    assert "exec-node-signature" not in html
    assert "const signatureText" not in html
    assert "node.note || detail?.note" in html


def test_render_uses_standard_flow_launch_cards() -> None:
    """Project flow entries must reuse the standard capability-card language."""

    html = render_html(build_architecture(ROOT))
    assert "flow-card-node" in html
    assert "flow-launch-grid" not in html
    assert "project-flow-mark" not in html
    assert "execution-node.kind-entry" not in html
    assert "window.__ARCHMAP_DATA__" in html


def test_render_ignores_layout_overrides_from_old_geometry() -> None:
    """Saved drag coordinates must not survive a default-geometry change."""

    html = render_html(build_architecture(ROOT))
    assert "const GEOMETRY_VERSION = 3;" in html
    assert "Number(value.geometryVersion) !== GEOMETRY_VERSION" in html
    assert "localStorage.removeItem(STORAGE_KEY)" in html


def test_render_exposes_dispatch_candidate_details() -> None:
    """Dispatch nodes must expose candidate navigation hooks in the detail panel."""

    html = render_html(build_architecture(ROOT))
    assert "dispatchCandidateList" in html
    assert "data-open-exec-candidate" in html
    assert "Dispatch candidates" in html
