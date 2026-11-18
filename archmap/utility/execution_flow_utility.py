"""Bounded P5 execution-flow assembly.

This module converts language-frontend skeletons into bundle-level execution
flows.  It deliberately does not expand free functions or functional-module
interfaces; those are opaque execution steps with source navigation targets.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable

from ..frontends.python.execution_utility import build_entry_execution_skeleton
from ..model.analysis_model import AnalysisResult
from ..model.call_model import CallSite
from ..model.contract_model import ContractModel
from .execution_layout_utility import layout_execution_flow


def _flow_key(entrypoint_id: str) -> str:
    return hashlib.sha1(entrypoint_id.encode("utf-8")).hexdigest()[:10]


def _module_meta(module_graphs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for graph in module_graphs:
        module_id = str(graph.get("moduleId") or "")
        result[module_id] = {
            "id": module_id,
            "name": str(graph.get("name") or module_id),
            "color": str(graph.get("color") or "#60a5fa"),
            "role": str(graph.get("role") or ""),
            "moduleKind": str(graph.get("moduleKind") or ""),
        }
    return result


def _capability_indexes(
    module_graphs: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_function: dict[str, dict[str, Any]] = {}
    by_constructor: dict[str, dict[str, Any]] = {}
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for graph in module_graphs:
        for node in graph.get("nodes", []):
            if node.get("kind") not in {"class", "function"}:
                continue
            for capability in node.get("providedApis", []):
                by_provider[str(capability.get("providerId") or "")].append(capability)
                function_id = capability.get("functionId")
                if function_id:
                    by_function[str(function_id)] = capability
                constructor_id = capability.get("constructorFunctionId")
                if constructor_id:
                    by_constructor[str(constructor_id)] = capability
    return by_function, by_constructor, by_provider


def _call_evidence(site: CallSite) -> dict[str, Any]:
    return {
        "callSiteId": site.id,
        "file": site.file,
        "line": site.line,
        "column": site.column,
        "callText": site.call_text,
        "calleeText": site.callee_text,
        "usageKind": site.usage_kind,
    }


def _interface_payload(
    capability: dict[str, Any],
    module_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    module_id = str(capability.get("moduleId") or "")
    meta = module_meta.get(module_id, {})
    function_id = capability.get("functionId") or capability.get("constructorFunctionId")
    return {
        "kind": "interface",
        "label": str(capability.get("display") or capability.get("signature") or capability.get("providerName") or ""),
        "functionId": function_id,
        "targetFunctionId": function_id,
        "capabilityId": capability.get("id"),
        "capabilityKind": capability.get("kind"),
        "providerId": capability.get("providerId"),
        "providerName": capability.get("providerName"),
        "providerRole": capability.get("providerRole"),
        "moduleId": module_id or None,
        "moduleName": meta.get("name") or module_id,
        "color": meta.get("color") or "#60a5fa",
        "note": capability.get("note") or "",
        "signature": capability.get("signature") or "",
        "targetFile": capability.get("file") or "",
        "targetLine": capability.get("line") or 0,
        "targetEndLine": capability.get("endLine") or capability.get("line") or 0,
    }


def _is_execution_dispatch_site(site: CallSite) -> bool:
    if site.resolved or site.external:
        return False
    if site.polymorphic or site.candidates:
        return True
    text = str(site.callee_text or "").strip()
    if text.endswith(".func") or text.startswith("getattr("):
        return True
    if text.endswith("]") and "[" in text and "]." not in text:
        return True
    return False


def _build_target_resolver(
    *,
    analysis: AnalysisResult,
    main_module_id: str,
    module_meta: dict[str, dict[str, Any]],
    capability_by_function: dict[str, dict[str, Any]],
    capability_by_constructor: dict[str, dict[str, Any]],
):
    def resolve(site: CallSite) -> dict[str, Any] | None:
        target = analysis.function_by_id.get(site.to_function_id or "")
        # A context-manager call resolves to the constructor but is projected as
        # the protocol capability node (for example ``with Spinner(...)``).
        if site.usage_kind in {"context_manager", "async_context_manager"} and target is not None:
            capability = capability_by_constructor.get(target.id)
            if capability is not None:
                return _interface_payload(capability, module_meta)
        if target is not None:
            if target.module_id == main_module_id:
                is_method = bool(target.class_name)
                is_dunder = target.name.startswith("__") and target.name.endswith("__")
                if not target.synthetic and (not is_method or not is_dunder):
                    meta = module_meta.get(target.module_id, {})
                    owner_class_id = (
                        f"cls:{target.module_name}.{target.class_name}"
                        if is_method
                        else None
                    )
                    return {
                        "kind": "free_function",
                        "callableKind": "method" if is_method else "function",
                        "ownerClassId": owner_class_id,
                        "ownerClassName": target.class_name,
                        "label": f"{target.name}()",
                        "functionId": target.id,
                        "targetFunctionId": target.id,
                        "capabilityId": None,
                        "moduleId": target.module_id,
                        "moduleName": meta.get("name", target.module_id),
                        "color": meta.get("color", "#f59e0b"),
                        "note": target.note,
                        "signature": target.signature,
                        "targetFile": target.file,
                        "targetLine": target.line,
                        "targetEndLine": target.end_line,
                    }
                return None
            capability = capability_by_function.get(target.id)
            if capability is not None:
                return _interface_payload(capability, module_meta)
            return None
        if not _is_execution_dispatch_site(site):
            return None
        meta = module_meta.get(site.from_module_id, {})
        candidates = list(site.candidates or [])
        return {
            "kind": "dispatch",
            "label": site.callee_text or site.call_text or "dispatch",
            "functionId": None,
            "targetFunctionId": None,
            "capabilityId": None,
            "moduleId": site.from_module_id,
            "moduleName": meta.get("name", site.from_module_id),
            "color": meta.get("color", "#60a5fa"),
            "note": "动态分发边界；候选不展开为执行分支。",
            "expression": site.callee_text or site.call_text or "",
            "candidateCount": len(candidates),
            "candidateSetComplete": False,
            "candidateSource": "polymorphic" if site.polymorphic else "unknown",
            "candidates": candidates,
        }

    return resolve


def build_execution_flows(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    entrypoints: list[dict[str, Any]],
    module_graphs: list[dict[str, Any]],
    contract_model: ContractModel | None = None,
) -> tuple[list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    """Build bounded execution flows for every entrypoint."""

    del contract_model  # capability facts are already projected into module graphs
    call_list = list(call_sites)
    module_meta = _module_meta(module_graphs)
    main_graph = next(
        (graph for graph in module_graphs if graph.get("moduleKind") == "main"),
        None,
    )
    main_module_id = str(main_graph.get("moduleId") if main_graph else analysis.config.main_module_id or "")
    capability_by_function, capability_by_constructor, _ = _capability_indexes(module_graphs)
    resolver = _build_target_resolver(
        analysis=analysis,
        main_module_id=main_module_id,
        module_meta=module_meta,
        capability_by_function=capability_by_function,
        capability_by_constructor=capability_by_constructor,
    )
    flows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    primary_id: str | None = None
    for index, entrypoint in enumerate(entrypoints):
        entry_id = str(entrypoint.get("functionId") or "")
        entry = analysis.function_by_id.get(entry_id)
        if entry is None:
            continue
        flow_key = _flow_key(entry_id)
        flow_id = f"exec-flow:{index + 1}:{flow_key}"
        skeleton = build_entry_execution_skeleton(
            analysis,
            call_list,
            entry,
            flow_id=flow_id,
            flow_key=flow_key,
            resolve_target=resolver,
            module_meta=module_meta,
        )
        skeleton["entrypointReason"] = str(entrypoint.get("reason") or "")
        skeleton["layout"] = layout_execution_flow(
            list(skeleton.get("nodes") or []),
            list(skeleton.get("edges") or []),
            flow_id,
        )
        flows.append(skeleton)
        diagnostics.extend(skeleton.get("diagnostics") or [])
        if primary_id is None:
            primary_id = flow_id
    return flows, primary_id, diagnostics
