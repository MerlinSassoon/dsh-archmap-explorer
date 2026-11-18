"""Deterministic LLM-annotation context and sidecar application helpers.

The module deliberately does not call a model.  It exposes the boundary used by
the DSH plugin: Python owns node identity, source excerpts and source hashes;
the plugin may only return semantic text for an existing node.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .render_utility import render_html


ANNOTATION_PROMPT_VERSION = "archmap-annotation-v1"
ANNOTATION_SYSTEM_PROMPT = (
    "你是 ArchMap 的源代码语义注释器。"
    "你只能依据用户提供的节点上下文和源码片段，不得虚构行为。\n"
    "输出必须是单个 JSON 对象，不要 Markdown，不要解释。\n"
    '格式：{"nodes":[{"nodeId":"...","summary":"一句中文职责摘要",'
    '\n"details":"2-4 句中文说明，覆盖职责、输入输出、'
    '关键步骤和异常/边界"}]}\n'
    "规则：\n"
    "1. 只能使用上下文中存在的 nodeId。\n"
    "2. summary 保持简洁；details 必须由源码证据支持。\n"
    "3. 不输出布局、调用统计、质量评价或无依据的推断。\n"
    "4. 保持 sourceHash 字段原样返回（如果提供）。"
)
SCOPE_KINDS: dict[str, frozenset[str]] = {
    "project": frozenset({"project"}),
    "modules": frozenset({"module"}),
    "functions": frozenset({"function"}),
    "all": frozenset({"project", "module", "function"}),
}
MANUAL_ANNOTATION_SOURCE = "manual"
HOST_ANNOTATION_SOURCE = "host-llm"
SUMMARY_MAX_CHARS = 240
DETAILS_MAX_CHARS = 2000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _load_annotations(path: Path | None) -> dict[str, Any]:
    if path and path.exists():
        data = _load_json(path)
        data.setdefault("version", 1)
        data.setdefault("nodes", {})
        if not isinstance(data.get("nodes"), dict):
            raise ValueError("annotations nodes must be an object")
        return data
    return {"version": 1, "nodes": {}}


def _clip(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)] + "…"


def _source_excerpt(detail: dict[str, Any], max_chars: int) -> str:
    """Return a bounded excerpt from the bundle's own function source text."""

    source = detail.get("source") or {}
    text = str(source.get("text") or "").strip()
    if not text:
        return ""
    return _clip(text, max_chars)


def _module_member_ids(bundle: dict[str, Any]) -> dict[str, list[str]]:
    """Collect function detail ids that belong to each module graph."""

    detail_ids = {str(detail.get("id")) for detail in bundle.get("functionDetails", [])}
    members: dict[str, set[str]] = {}
    for module in bundle.get("projectGraph", {}).get("modules", []):
        module_id = str(module.get("id") or "")
        if not module_id:
            continue
        bucket = members.setdefault(module_id, set())
        for function_id in module.get("functions", []) or []:
            if str(function_id) in detail_ids:
                bucket.add(str(function_id))
    for graph in bundle.get("moduleGraphs", []):
        module_id = str(graph.get("moduleId") or "")
        if not module_id:
            continue
        bucket = members.setdefault(module_id, set())
        for node in graph.get("nodes", []) or []:
            if node.get("kind") != "function":
                continue
            function_id = str(node.get("functionDetailId") or node.get("id") or "")
            if function_id in detail_ids:
                bucket.add(function_id)
    return {module_id: sorted(ids) for module_id, ids in members.items()}


def _node_index(bundle: dict[str, Any], max_chars: int = 6000) -> dict[str, dict[str, Any]]:
    """Build the authoritative annotation target index from bundle facts."""

    details = {
        str(detail.get("id")): detail
        for detail in bundle.get("functionDetails", [])
        if detail.get("id")
    }
    members = _module_member_ids(bundle)
    index: dict[str, dict[str, Any]] = {}

    for detail_id, detail in sorted(details.items()):
        index[detail_id] = {
            "nodeId": detail_id,
            "kind": "function",
            "name": str(detail.get("name") or ""),
            "note": str(detail.get("note") or ""),
            "module": str(detail.get("moduleId") or ""),
            "file": str(detail.get("file") or ""),
            "line": int(detail.get("line") or 1),
            "endLine": int(detail.get("endLine") or detail.get("line") or 1),
            "signature": str(detail.get("signature") or ""),
            "sourceHash": str(detail.get("sourceHash") or ""),
            "sourceExcerpt": _source_excerpt(detail, max_chars),
            "relatedFunctions": [],
        }

    modules_by_id = {
        str(module.get("id")): module
        for module in bundle.get("projectGraph", {}).get("modules", [])
        if module.get("id")
    }
    for module_id in sorted(set(modules_by_id) | set(members)):
        module = modules_by_id.get(module_id, {})
        member_ids = members.get(module_id, [])
        member_hashes = sorted(
            str(details[function_id].get("sourceHash") or "")
            for function_id in member_ids
            if function_id in details
        )
        note = str(module.get("note") or "")
        index[module_id] = {
            "nodeId": module_id,
            "kind": "module",
            "name": str(module.get("name") or module_id),
            "note": note,
            "module": module_id,
            "file": "",
            "line": 1,
            "endLine": 1,
            "signature": "",
            "sourceHash": _hash({"functions": member_hashes, "note": note}),
            "sourceExcerpt": "",
            "relatedFunctions": member_ids,
        }

    project = bundle.get("project") or {}
    project_name = str(project.get("name") or "")
    project_hash = str(project.get("fingerprint") or "") or _hash(project)
    index[project_name] = {
        "nodeId": project_name,
        "kind": "project",
        "name": project_name,
        "note": "",
        "module": "",
        "file": "",
        "line": 1,
        "endLine": 1,
        "signature": "",
        "sourceHash": project_hash,
        "sourceExcerpt": "",
        "relatedFunctions": [],
    }
    return index


def annotation_context(
    bundle_path: Path | str,
    scope: str = "functions",
    node_ids: list[str] | None = None,
    max_nodes: int = 50,
    max_chars_per_node: int = 6000,
    include_source: bool = True,
    annotations_path: Path | str | None = None,
) -> dict[str, Any]:
    """Build a bounded, deterministic annotation context for the host model."""

    bundle_file = Path(bundle_path)
    bundle = _load_json(bundle_file)
    wanted_kinds = SCOPE_KINDS.get(scope)
    if wanted_kinds is None:
        raise ValueError(f"unsupported annotation scope: {scope}")
    if max_nodes < 1:
        raise ValueError("max_nodes must be a positive integer")
    if max_chars_per_node < 1:
        raise ValueError("max_chars_per_node must be a positive integer")

    annotation_file = (
        Path(annotations_path)
        if annotations_path is not None
        else bundle_file.parent / "llm-annotations.json"
    )
    annotations = _load_annotations(annotation_file)
    index = _node_index(bundle, max_chars=max_chars_per_node)

    requested = {str(node_id) for node_id in (node_ids or [])}
    kind_order = {"project": 0, "module": 1, "function": 2}
    candidate_ids: list[str] = []
    for node_id in sorted(index, key=lambda item: (kind_order.get(index[item]["kind"], 9), item)):
        node = index[node_id]
        if requested and node_id not in requested:
            continue
        if node["kind"] not in wanted_kinds:
            continue
        candidate_ids.append(node_id)

    selected_ids = candidate_ids[:max_nodes]
    nodes: list[dict[str, Any]] = []
    existing_nodes = annotations.get("nodes") or {}
    for node_id in selected_ids:
        node = dict(index[node_id])
        if not include_source or node["kind"] != "function":
            node["sourceExcerpt"] = ""
        existing = existing_nodes.get(node_id)
        node["existingAnnotation"] = existing if isinstance(existing, dict) else None
        nodes.append(node)

    missing_ids = sorted(requested - set(index))
    return {
        "promptVersion": ANNOTATION_PROMPT_VERSION,
        "systemPrompt": ANNOTATION_SYSTEM_PROMPT,
        "project": bundle.get("project") or {},
        "nodes": nodes,
        "requestedNodes": len(requested) if requested else None,
        "missingNodeIds": missing_ids,
        "truncated": len(candidate_ids) > len(selected_ids),
    }


def _normalize_proposal(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = proposal.get("nodes")
    if isinstance(nodes, dict):
        return [
            {"nodeId": str(node_id), **value}
            for node_id, value in nodes.items()
            if isinstance(value, dict)
        ]
    if isinstance(nodes, list):
        return [item for item in nodes if isinstance(item, dict)]
    raise ValueError("annotation proposal must contain a nodes object or array")


def apply_annotations(
    bundle_path: Path | str,
    proposal: dict[str, Any],
    annotations_path: Path | str | None = None,
    render: bool = True,
    force: bool = False,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    """Validate a model proposal and merge it into the annotation sidecar.

    Node identity and source hashes come exclusively from the current bundle.
    Existing annotations are preserved unless ``force=True``.
    """

    bundle_file = Path(bundle_path)
    bundle = _load_json(bundle_file)
    output_path = (
        Path(annotations_path)
        if annotations_path is not None
        else bundle_file.parent / "llm-annotations.json"
    )
    existing = _load_annotations(output_path)
    index = _node_index(bundle)

    applied: list[str] = []
    skipped: list[dict[str, str]] = []
    seen_nodes: set[str] = set()
    for item in _normalize_proposal(proposal):
        node_id = str(item.get("nodeId") or "").strip()
        summary = str(item.get("summary") or "").strip()
        details = str(item.get("details") or "").strip()

        if not node_id or node_id not in index:
            skipped.append({"nodeId": node_id, "reason": "UNKNOWN_NODE"})
            continue
        if node_id in seen_nodes:
            skipped.append({"nodeId": node_id, "reason": "DUPLICATE_PROPOSAL_NODE"})
            continue
        seen_nodes.add(node_id)
        if not summary:
            skipped.append({"nodeId": node_id, "reason": "EMPTY_SUMMARY"})
            continue

        node = index[node_id]
        expected_hash = str(node.get("sourceHash") or "")
        provided_hash = str(item.get("sourceHash") or expected_hash)
        if expected_hash and provided_hash and provided_hash != expected_hash:
            skipped.append({"nodeId": node_id, "reason": "STALE_SOURCE_HASH"})
            continue

        previous = (existing.get("nodes") or {}).get(node_id)
        if isinstance(previous, dict) and not force:
            reason = (
                "MANUAL_ANNOTATION_PRESERVED"
                if str(previous.get("source") or "") == MANUAL_ANNOTATION_SOURCE
                else "EXISTING_ANNOTATION_PRESERVED"
            )
            skipped.append({"nodeId": node_id, "reason": reason})
            continue

        existing.setdefault("nodes", {})[node_id] = {
            "summary": summary[:SUMMARY_MAX_CHARS],
            "details": details[:DETAILS_MAX_CHARS],
            "sourceHash": expected_hash,
            "source": str(item.get("source") or HOST_ANNOTATION_SOURCE),
            "provider": str(provider or ""),
            "model": str(model or ""),
            "promptVersion": prompt_version or ANNOTATION_PROMPT_VERSION,
            "generatedAt": _now(),
        }
        applied.append(node_id)

    existing["version"] = 1
    existing["updatedAt"] = _now()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    html_path = bundle_file.parent / "architecture.html"
    if render:
        html_path.write_text(render_html(bundle, existing), encoding="utf-8")

    reasons: dict[str, int] = {}
    for item in skipped:
        reason = item["reason"]
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "ok": True,
        "applied": len(applied),
        "appliedNodeIds": applied,
        "skipped": skipped,
        "stats": {
            "applied": len(applied),
            "skipped": len(skipped),
            "reasons": reasons,
        },
        "annotationsPath": str(output_path),
        "htmlPath": str(html_path) if render else None,
    }
