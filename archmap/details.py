from __future__ import annotations

import ast
import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable

from .analysis import AnalysisResult, FunctionInfo
from .callsites import CallSite

MAX_SOURCE_CHARS = 24000


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
    }


def build_function_details(
    analysis: AnalysisResult, call_sites: Iterable[CallSite]
) -> list[dict[str, Any]]:
    calls = list(call_sites)
    callers_by_function: dict[str, list[CallSite]] = defaultdict(list)
    callees_by_function: dict[str, list[CallSite]] = defaultdict(list)
    for site in calls:
        callers_by_function[site.to_function_id or ""].append(site)
        callees_by_function[site.from_function_id].append(site)

    details: list[dict[str, Any]] = []
    for fn in sorted(analysis.functions, key=lambda item: item.id):
        source = _source_slice(analysis, fn)
        source_hash = _json_hash(
            {
                "id": fn.id,
                "signature": fn.signature,
                "note": fn.note,
                "source": source["text"],
            }
        )
        callers = [
            _caller_entry(analysis, site)
            for site in sorted(
                callers_by_function.get(fn.id, []),
                key=lambda item: (item.file, item.line, item.column, item.id),
            )
        ]
        callees = [
            _callee_entry(analysis, site)
            for site in sorted(
                callees_by_function.get(fn.id, []),
                key=lambda item: (item.line, item.column, item.id),
            )
        ]
        details.append(
            {
                "id": fn.id,
                "name": fn.name,
                "qualifiedName": f"{fn.module_name}.{fn.qualname}",
                "module": fn.module_name,
                "moduleId": fn.module_id,
                "ownerClassId": _owner_class_id(fn),
                "methodKind": fn.method_kind,
                "visibility": fn.visibility,
                "isAbstract": fn.is_abstract,
                "isAsync": fn.is_async,
                "file": fn.file,
                "line": fn.line,
                "endLine": fn.end_line,
                "signature": fn.signature,
                "returns": _unparse(getattr(fn.node, "returns", None)),
                "raises": _raises(fn),
                "note": fn.note,
                "source": source,
                "sourceHash": source_hash,
                "callers": callers,
                "callees": callees,
                "callerCount": len(callers),
                "calleeCount": len(callees),
            }
        )
    return details
