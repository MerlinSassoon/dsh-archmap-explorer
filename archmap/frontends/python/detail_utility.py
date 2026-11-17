"""Python-frontend function-detail stage implementation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from ...model.analysis_model import AnalysisResult
from ...model.call_model import CallSite
from ...utility.detail_utility import (
    _callee_entry,
    _caller_entry,
    _json_hash,
    _owner_class_id,
    _raises,
    _source_slice,
    _unparse,
)


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
                "apiExposure": fn.api_exposure,
                "apiExposureSource": fn.api_exposure_source,
                "apiExposureConfidence": fn.api_exposure_confidence,
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
