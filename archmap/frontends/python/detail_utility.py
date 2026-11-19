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


def _unresolved_caller_entry(analysis: AnalysisResult, site: CallSite) -> dict[str, Any]:
    entry = _caller_entry(analysis, site)
    entry.update(
        {
            "callSiteId": site.id,
            "resolved": False,
            "resolutionReason": "callee-name-match",
            "confidence": "low",
        }
    )
    return entry


def _callee_tail(callee_text: str) -> str:
    text = str(callee_text or "").strip().split("(", 1)[0].strip()
    return text.rsplit(".", 1)[-1] if text else ""


def build_function_details(
    analysis: AnalysisResult, call_sites: Iterable[CallSite]
) -> list[dict[str, Any]]:
    calls = list(call_sites)
    callers_by_function: dict[str, list[CallSite]] = defaultdict(list)
    callees_by_function: dict[str, list[CallSite]] = defaultdict(list)
    polymorphic_callers_by_function: dict[str, list[CallSite]] = defaultdict(list)
    unresolved_by_callee_name: dict[str, list[CallSite]] = defaultdict(list)
    for site in calls:
        if not site.resolved and not site.external:
            tail = _callee_tail(site.callee_text)
            if tail:
                unresolved_by_callee_name[tail].append(site)
    for site in calls:
        callers_by_function[site.to_function_id or ""].append(site)
        callees_by_function[site.from_function_id].append(site)
        if site.polymorphic:
            for candidate_id in site.candidates:
                polymorphic_callers_by_function[candidate_id].append(site)

    class_by_id = {
        f"cls:{cls.module_name}.{cls.qualname}": cls for cls in analysis.classes
    }
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
        override_of = None
        overridden_by: list[str] = []
        if fn.class_name:
            owner_id = _owner_class_id(fn)
            owner = class_by_id.get(owner_id or "")
            if owner is not None:
                for ancestor_id in owner.mro_class_ids[1:]:
                    ancestor = class_by_id.get(ancestor_id)
                    if ancestor is not None and fn.name in ancestor.methods:
                        override_of = ancestor.methods[fn.name].id
                        break
                for subclass_id in owner.subclass_ids:
                    subclass = class_by_id.get(subclass_id)
                    if subclass is not None and fn.name in subclass.methods:
                        overridden_by.append(subclass.methods[fn.name].id)
        polymorphic_callers = [
            _caller_entry(analysis, site)
            for site in sorted(
                polymorphic_callers_by_function.get(fn.id, []),
                key=lambda item: (item.file, item.line, item.column, item.id),
            )
        ]
        polymorphic_callees = [
            _callee_entry(analysis, site)
            for site in sorted(
                (site for site in callees_by_function.get(fn.id, []) if site.polymorphic),
                key=lambda item: (item.line, item.column, item.id),
            )
        ]
        unresolved_callers = [
            _unresolved_caller_entry(analysis, site)
            for site in sorted(
                (
                    site
                    for site in unresolved_by_callee_name.get(fn.name, [])
                    if site.from_function_id != fn.id
                ),
                key=lambda item: (item.file, item.line, item.column, item.id),
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
                "overrideOfFunctionId": override_of,
                "overriddenByFunctionIds": sorted(set(overridden_by)),
                "polymorphicCallers": polymorphic_callers,
                "polymorphicCallees": polymorphic_callees,
                "polymorphicCallerCount": len(polymorphic_callers),
                "polymorphicCalleeCount": len(polymorphic_callees),
                "unresolvedCallers": unresolved_callers,
                "unresolvedCallerCount": len(unresolved_callers),
            }
        )
    return details
