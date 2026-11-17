"""Function-detail and source-slicing helpers."""

from __future__ import annotations

import ast
import hashlib
import json
from typing import Any

from ..model.analysis_model import AnalysisResult, FunctionInfo
from ..config.detail_config import MAX_SOURCE_CHARS
from ..model.call_model import CallSite


def _json_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _source_slice(analysis: AnalysisResult, fn: FunctionInfo) -> dict[str, Any]:
    lines = analysis.line_cache.get(fn.file, [])
    start = max(1, int(fn.line or 1))
    end = max(start, int(fn.end_line or start))
    text = "\n".join(lines[start - 1 : end])
    truncated = len(text) > MAX_SOURCE_CHARS
    if truncated:
        text = text[: MAX_SOURCE_CHARS - 1] + "…"
    return {
        "text": text,
        "startLine": start,
        "endLine": end,
        "truncated": truncated,
        "language": "python",
    }


def _raises(fn: FunctionInfo) -> list[str]:
    names: set[str] = set()
    for stmt in getattr(fn.node, "body", []):
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise) and node.exc is not None:
                text = _unparse(node.exc)
                if text:
                    names.add(text)
    return sorted(names)


def _owner_class_id(fn: FunctionInfo) -> str | None:
    if not fn.class_name:
        return None
    return f"cls:{fn.module_name}.{fn.class_name}"


def _caller_entry(analysis: AnalysisResult, site: CallSite) -> dict[str, Any]:
    caller = analysis.function_by_id.get(site.from_function_id)
    return {
        "functionId": site.from_function_id,
        "name": caller.name if caller else site.from_function_id,
        "qualifiedName": f"{caller.module_name}.{caller.qualname}" if caller else "",
        "moduleId": caller.module_id if caller else site.from_module_id,
        "file": site.file,
        "line": site.line,
        "column": site.column,
        "calleeText": site.callee_text,
        "callText": site.call_text,
        "confidence": site.confidence,
        "polymorphic": site.polymorphic,
        "dispatchKind": site.dispatch_kind,
    }


def _callee_entry(analysis: AnalysisResult, site: CallSite) -> dict[str, Any]:
    target = analysis.function_by_id.get(site.to_function_id or "")
    return {
        "functionId": site.to_function_id,
        "name": target.name if target else site.callee_text,
        "qualifiedName": f"{target.module_name}.{target.qualname}" if target else site.callee_text,
        "moduleId": target.module_id if target else site.to_module_id,
        "file": target.file if target else site.file,
        "line": site.line,
        "column": site.column,
        "calleeText": site.callee_text,
        "callText": site.call_text,
        "resolved": site.resolved,
        "external": site.external,
        "recursive": site.recursive,
        "confidence": site.confidence,
        "candidates": list(site.candidates),
        "polymorphic": site.polymorphic,
        "dispatchKind": site.dispatch_kind,
    }
