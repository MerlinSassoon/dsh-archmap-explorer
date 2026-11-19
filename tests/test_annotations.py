from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from archmap.annotations import annotation_context, apply_annotations
from archmap.managers.pipeline_manager import PipelineManager

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def _write_bundle(tmp_path: Path) -> tuple[Path, dict]:
    bundle = PipelineManager().build_architecture(ROOT)
    out = tmp_path / "bundle"
    out.mkdir()
    bundle_path = out / "architecture.json"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    return bundle_path, bundle


def test_annotation_context_is_source_backed_and_bounded(tmp_path: Path) -> None:
    """Context must expose bundle-owned identity, source hash and bounded source."""
    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")

    context = annotation_context(
        bundle_path,
        scope="functions",
        node_ids=["fn:app.main.main"],
        max_chars_per_node=80,
    )

    assert context["promptVersion"] == "archmap-annotation-v1"
    assert context["systemPrompt"]
    assert context["project"]["name"] == "student_demo"
    assert context["requestedNodes"] == 1
    assert context["truncated"] is False
    assert context["missingNodeIds"] == []
    assert len(context["nodes"]) == 1

    node = context["nodes"][0]
    assert node["nodeId"] == "fn:app.main.main"
    assert node["signature"] == detail["signature"]
    assert node["note"] == detail["note"]
    assert node["sourceHash"] == detail["sourceHash"]
    assert node["sourceExcerpt"]
    assert len(node["sourceExcerpt"]) <= 80
    assert node["existingAnnotation"] is None


def test_annotation_context_scopes_projects_modules_and_nodes(tmp_path: Path) -> None:
    """Every scope must select only its declared node kinds and enforce limits."""
    bundle_path, bundle = _write_bundle(tmp_path)
    project = annotation_context(bundle_path, scope="project")
    modules = annotation_context(bundle_path, scope="modules")
    functions = annotation_context(bundle_path, scope="functions", max_nodes=2)

    assert [node["kind"] for node in project["nodes"]] == ["project"]
    assert {node["nodeId"] for node in modules["nodes"]} == {
        module["id"] for module in bundle["projectGraph"]["modules"]
    }
    assert all(node["kind"] == "function" for node in functions["nodes"])
    assert len(functions["nodes"]) == 2
    assert functions["truncated"] is True


def test_annotation_context_includes_existing_annotation_summary(tmp_path: Path) -> None:
    """Existing sidecar entries must be visible to the model for preservation."""
    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")
    sidecar = bundle_path.parent / "llm-annotations.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "nodes": {
                    "fn:app.main.main": {
                        "summary": "已有摘要",
                        "details": "已有详情",
                        "sourceHash": detail["sourceHash"],
                        "source": "manual",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    context = annotation_context(bundle_path, node_ids=["fn:app.main.main"])
    assert context["nodes"][0]["existingAnnotation"]["summary"] == "已有摘要"
    assert context["nodes"][0]["existingAnnotation"]["source"] == "manual"


def test_apply_annotations_uses_bundle_source_hash_and_rerenders(tmp_path: Path) -> None:
    """Apply must write the bundle hash and inject the sidecar into HTML."""
    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")

    result = apply_annotations(
        bundle_path,
        {
            "nodes": [
                {
                    "nodeId": "fn:app.main.main",
                    "summary": "程序主入口",
                    "details": "加载数据并处理学生记录。",
                }
            ]
        },
        provider="deepseek-official",
        model="deepseek-flash",
    )

    assert result["ok"] is True
    assert result["applied"] == 1
    assert result["skipped"] == []
    sidecar = json.loads((bundle_path.parent / "llm-annotations.json").read_text(encoding="utf-8"))
    annotation = sidecar["nodes"]["fn:app.main.main"]
    assert annotation["summary"] == "程序主入口"
    assert annotation["sourceHash"] == detail["sourceHash"]
    assert annotation["source"] == "host-llm"
    assert annotation["provider"] == "deepseek-official"
    assert annotation["model"] == "deepseek-flash"
    html = (bundle_path.parent / "architecture.html").read_text(encoding="utf-8")
    assert "程序主入口" in html


def test_apply_rejects_stale_hash_unknown_nodes_and_empty_summary(tmp_path: Path) -> None:
    """Invalid proposals must be skipped with actionable reason codes."""
    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")

    result = apply_annotations(
        bundle_path,
        {
            "nodes": {
                "fn:app.main.main": {
                    "summary": "摘要",
                    "details": "详情",
                    "sourceHash": "sha256:" + "0" * 64,
                },
                "fn:missing": {"summary": "摘要", "details": "详情"},
                "fn:app.repo.read_all": {"summary": " ", "details": "详情"},
            }
        },
        render=False,
    )

    assert result["applied"] == 0
    reasons = {item["nodeId"]: item["reason"] for item in result["skipped"]}
    assert reasons["fn:app.main.main"] == "STALE_SOURCE_HASH"
    assert reasons["fn:missing"] == "UNKNOWN_NODE"
    assert reasons["fn:app.repo.read_all"] == "EMPTY_SUMMARY"
    assert result["htmlPath"] is None


def test_apply_preserves_existing_annotations_unless_forced(tmp_path: Path) -> None:
    """Manual annotations survive by default and force is the only override."""
    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")
    sidecar = bundle_path.parent / "llm-annotations.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "nodes": {
                    "fn:app.main.main": {
                        "summary": "人工摘要",
                        "details": "人工详情",
                        "sourceHash": detail["sourceHash"],
                        "source": "manual",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proposal = {
        "nodes": [
            {
                "nodeId": "fn:app.main.main",
                "summary": "模型摘要",
                "details": "模型详情",
                "sourceHash": detail["sourceHash"],
            }
        ]
    }

    preserved = apply_annotations(bundle_path, proposal, render=False)
    assert preserved["applied"] == 0
    assert preserved["skipped"] == [
        {"nodeId": "fn:app.main.main", "reason": "MANUAL_ANNOTATION_PRESERVED"}
    ]

    forced = apply_annotations(bundle_path, proposal, render=False, force=True)
    assert forced["applied"] == 1
    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    assert saved["nodes"]["fn:app.main.main"]["summary"] == "模型摘要"


def test_apply_preserves_host_annotations_unless_forced(tmp_path: Path) -> None:
    """Previously generated annotations are also preserved without force."""
    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")
    sidecar = bundle_path.parent / "llm-annotations.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "nodes": {
                    "fn:app.main.main": {
                        "summary": "旧模型摘要",
                        "details": "旧模型详情",
                        "sourceHash": detail["sourceHash"],
                        "source": "host-llm",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proposal = {
        "nodes": [
            {
                "nodeId": "fn:app.main.main",
                "summary": "新模型摘要",
                "details": "新模型详情",
                "sourceHash": detail["sourceHash"],
            }
        ]
    }

    preserved = apply_annotations(bundle_path, proposal, render=False)
    assert preserved["applied"] == 0
    assert preserved["skipped"] == [
        {"nodeId": "fn:app.main.main", "reason": "EXISTING_ANNOTATION_PRESERVED"}
    ]

    forced = apply_annotations(bundle_path, proposal, render=False, force=True)
    assert forced["applied"] == 1
    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    assert saved["nodes"]["fn:app.main.main"]["summary"] == "新模型摘要"


def test_annotations_cli_context_and_apply(tmp_path: Path) -> None:
    """CLI JSON commands must form a complete context-to-sidecar workflow."""
    bundle_path, _bundle = _write_bundle(tmp_path)
    context_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "archmap",
            "annotations",
            "context",
            str(bundle_path),
            "--scope",
            "functions",
            "--node-id",
            "fn:app.main.main",
            "--json",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert context_result.returncode == 0, context_result.stderr
    context = json.loads(context_result.stdout)
    node = context["nodes"][0]

    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "nodeId": node["nodeId"],
                        "summary": "程序主入口",
                        "details": "加载数据并处理学生记录。",
                        "sourceHash": node["sourceHash"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "archmap",
            "annotations",
            "apply",
            str(bundle_path),
            "--proposal",
            str(proposal_path),
            "--provider",
            "deepseek-official",
            "--model",
            "deepseek-flash",
            "--json",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    applied = json.loads(apply_result.stdout)
    assert applied["applied"] == 1
    assert Path(applied["annotationsPath"]).exists()
    assert Path(applied["htmlPath"]).exists()


def test_annotation_context_filters_before_limit_and_reports_statuses(tmp_path: Path) -> None:
    """Refresh mode must select eligible nodes before applying max_nodes."""

    bundle_path, bundle = _write_bundle(tmp_path)
    details = [detail for detail in bundle["functionDetails"] if detail["id"].startswith("fn:")]
    assert len(details) >= 3
    first_id = details[0]["id"]
    second_id = details[1]["id"]
    missing_id = details[-1]["id"]
    sidecar = bundle_path.parent / "llm-annotations.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "nodes": {
                    detail["id"]: {
                        "summary": "已有摘要",
                        "details": "已有详情",
                        "sourceHash": (
                            "sha256:" + "0" * 64
                            if detail["id"] == second_id
                            else detail["sourceHash"]
                        ),
                        "source": "host-llm",
                    }
                    for detail in details
                    if detail["id"] != missing_id
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    context = annotation_context(
        bundle_path,
        scope="functions",
        max_nodes=1,
        refresh_mode="stale",
    )

    assert context["refreshMode"] == "stale"
    assert context["totalCandidates"] == len(details)
    assert context["eligibleCount"] == 2
    assert context["selectedCount"] == 1
    assert context["remainingCount"] == 1
    assert context["truncated"] is True
    assert context["statusCounts"]["missing"] == 1
    assert context["statusCounts"]["stale"] == 1
    assert context["nodes"][0]["annotationStatus"] in {"stale", "missing"}

    missing_only = annotation_context(
        bundle_path,
        scope="functions",
        max_nodes=1,
        refresh_mode="missing",
    )
    assert missing_only["eligibleCount"] == 1
    assert missing_only["nodes"][0]["nodeId"] == missing_id
    assert missing_only["statusCounts"]["manual-preserved"] == 0
    assert first_id != missing_id


def test_annotation_context_marks_manual_annotations_preserved(tmp_path: Path) -> None:
    """Manual annotations stay out of stale refresh selection."""

    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")
    sidecar = bundle_path.parent / "llm-annotations.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "nodes": {
                    "fn:app.main.main": {
                        "summary": "人工摘要",
                        "details": "人工详情",
                        "sourceHash": "sha256:" + "0" * 64,
                        "source": "manual",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    context = annotation_context(
        bundle_path,
        scope="functions",
        max_nodes=1,
        refresh_mode="stale",
        node_ids=["fn:app.main.main"],
    )

    assert context["statusCounts"]["manual-preserved"] == 1
    assert context["eligibleCount"] == 0
    assert context["nodes"] == []
    assert detail["id"] == "fn:app.main.main"


def test_apply_refreshes_stale_machine_annotation_without_force(tmp_path: Path) -> None:
    """A stale host annotation is data loss, not a user-owned manual override."""

    bundle_path, bundle = _write_bundle(tmp_path)
    detail = next(item for item in bundle["functionDetails"] if item["id"] == "fn:app.main.main")
    sidecar = bundle_path.parent / "llm-annotations.json"
    sidecar.write_text(
        json.dumps(
            {
                "version": 1,
                "nodes": {
                    "fn:app.main.main": {
                        "summary": "旧模型摘要",
                        "details": "旧模型详情",
                        "sourceHash": "sha256:" + "0" * 64,
                        "source": "host-llm",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = apply_annotations(
        bundle_path,
        {
            "nodes": [
                {
                    "nodeId": "fn:app.main.main",
                    "summary": "新模型摘要",
                    "details": "新模型详情",
                    "sourceHash": detail["sourceHash"],
                }
            ]
        },
        render=False,
    )

    assert result["applied"] == 1
    assert result["skipped"] == []
    saved = json.loads(sidecar.read_text(encoding="utf-8"))
    assert saved["nodes"]["fn:app.main.main"]["summary"] == "新模型摘要"
