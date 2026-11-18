"""Bounded P5 execution-flow assembly.

This module converts language-frontend skeletons into bundle-level execution
flows.  It deliberately does not expand free functions or functional-module
interfaces; those are opaque execution steps with source navigation targets.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Iterable

from ..config.project_config import DispatchHint
from ..frontends.python.execution_utility import build_entry_execution_skeleton
from ..model.analysis_model import AnalysisResult
from ..model.call_model import CallSite
from ..model.contract_model import ContractModel
from .call_resolution_utility import DispatchResolver, is_dynamic_dispatch_site, resolve_function_ref
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


def _build_target_resolver(
    *,
    analysis: AnalysisResult,
    module_meta: dict[str, dict[str, Any]],
    capability_by_function: dict[str, dict[str, Any]],
    capability_by_constructor: dict[str, dict[str, Any]],
    dispatch_resolver: DispatchResolver,
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
            capability = capability_by_function.get(target.id)
            if capability is not None:
                return _interface_payload(capability, module_meta)
            is_method = bool(target.class_name)
            is_dunder = target.name.startswith("__") and target.name.endswith("__")
            if target.synthetic or (is_method and is_dunder):
                return None
            meta = module_meta.get(target.module_id, {})
            owner_class_id = (
                f"cls:{target.module_name}.{target.class_name}"
                if is_method
                else None
            )
            signature = target.signature.strip()
            for prefix in ("async def ", "def "):
                if signature.startswith(prefix):
                    signature = signature[len(prefix):]
                    break
            if not is_method and " -> " in signature:
                signature = signature.split(" -> ", 1)[0].strip()
            label = f"{target.name}()" if is_method else (signature or f"{target.name}()")
            return {
                "kind": "free_function",
                "callableKind": "method" if is_method else "function",
                "ownerClassId": owner_class_id,
                "ownerClassName": target.class_name,
                "label": label,
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
        if not (site.polymorphic or is_dynamic_dispatch_site(site)):
            return None
        meta = module_meta.get(site.from_module_id, {})
        resolution = dispatch_resolver.resolve(site)
        candidates = resolution.candidates
        return {
            "kind": "dispatch",
            "label": site.callee_text or site.call_text or "dispatch",
            "functionId": None,
            "targetFunctionId": None,
            "capabilityId": None,
            "moduleId": site.from_module_id,
            "moduleName": meta.get("name", site.from_module_id),
            "color": meta.get("color", "#60a5fa"),
            "note": "动态分发边界；候选详情见节点面板，不展开为执行分支。",
            "expression": site.callee_text or site.call_text or "",
            "candidateCount": len(candidates),
            "candidateSetComplete": resolution.candidate_set_complete,
            "candidateSource": resolution.candidate_source,
            "candidates": candidates,
            "unresolvedReason": resolution.unresolved_reason,
        }

    return resolve


_SCOPE_CONTROL_KINDS = {
    "entry",
    "exit",
    "branch",
    "multi_branch",
    "loop",
    "break",
    "continue",
    "return",
    "dispatch",
}


def _scope_interface_summary(
    nodes: list[dict[str, Any]],
    extra_hints: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Collect external capability interfaces reached by a scope."""

    merged: dict[str, dict[str, Any]] = {}
    candidates = [
        node for node in nodes if node.get("kind") == "interface"
    ] + list(extra_hints or [])
    for node in candidates:
        if node.get("kind") != "interface" and node.get("hint") is not True:
            continue
        capability_id = str(node.get("capabilityId") or "")
        label = str(node.get("label") or node.get("capabilityId") or "")
        key = capability_id or f"{node.get('moduleId')}:{label}"
        item = merged.setdefault(
            key,
            {
                "capabilityId": capability_id or None,
                "label": label,
                "moduleId": str(node.get("moduleId") or ""),
                "moduleName": str(node.get("moduleName") or node.get("moduleId") or ""),
                "providerName": str(node.get("providerName") or ""),
                "capabilityKind": str(node.get("capabilityKind") or ""),
                "callCount": 0,
                "confidence": "high",
            },
        )
        item["callCount"] = int(item.get("callCount", 0)) + 1
    return sorted(
        merged.values(),
        key=lambda item: (str(item.get("moduleId") or ""), str(item.get("label") or "")),
    )


def _helper_interface_hints(
    *,
    analysis: AnalysisResult,
    call_sites: list[CallSite],
    resolver,
    nodes: list[dict[str, Any]],
    root_module_id: str,
) -> list[dict[str, Any]]:
    """Collect one-hop external interfaces behind compact internal helpers.

    The helper itself remains an atomic execution node.  Its directly invoked
    capability interfaces are attached as hints so the scope still answers
    "which external APIs are involved" without recursively expanding the helper.
    """

    calls_by_from: dict[str, list[CallSite]] = defaultdict(list)
    for site in call_sites:
        if site.from_function_id:
            calls_by_from[str(site.from_function_id)].append(site)
    hints: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("kind") != "free_function":
            continue
        helper_id = str(node.get("targetFunctionId") or node.get("functionId") or "")
        helper = analysis.function_by_id.get(helper_id)
        if helper is None or helper.module_id != root_module_id:
            continue
        node_hints: list[dict[str, Any]] = []
        for site in sorted(calls_by_from.get(helper_id, []), key=lambda item: (item.line, item.column)):
            resolved = resolver(site)
            if not resolved or resolved.get("kind") != "interface":
                continue
            target_module_id = str(resolved.get("moduleId") or "")
            if not target_module_id:
                continue
            item = {
                "capabilityId": resolved.get("capabilityId"),
                "label": str(resolved.get("label") or ""),
                "moduleId": target_module_id,
                "moduleName": str(resolved.get("moduleName") or target_module_id),
                "providerName": str(resolved.get("providerName") or ""),
                "capabilityKind": str(resolved.get("capabilityKind") or ""),
                "callCount": 1,
                "confidence": "high",
                "hint": True,
                "helperFunctionId": helper_id,
                "helperLabel": str(node.get("label") or helper.name),
            }
            node_hints.append(item)
            hints.append(item)
        if node_hints:
            node["interfaceHints"] = node_hints
    return hints


def _contract_scope_node(
    node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Remove one non-control call node while preserving a simple flow path."""

    incoming = [edge for edge in edges if str(edge.get("to") or "") == node_id]
    outgoing = [edge for edge in edges if str(edge.get("from") or "") == node_id]
    if len(incoming) > 1 or len(outgoing) > 1:
        return None
    remaining_nodes = [node for node in nodes if str(node.get("id") or "") != node_id]
    remaining_edges = [
        edge
        for edge in edges
        if str(edge.get("to") or "") != node_id
        and str(edge.get("from") or "") != node_id
    ]
    if incoming and outgoing:
        source_edge = incoming[0]
        target_edge = outgoing[0]
        new_edge = {
            **source_edge,
            "id": f"{source_edge.get('id')}:skip:{node_id}",
            "to": target_edge.get("to"),
            "label": target_edge.get("label") or source_edge.get("label") or "",
            "kind": source_edge.get("kind") or target_edge.get("kind") or "next",
        }
        remaining_edges.append(new_edge)
    return remaining_nodes, remaining_edges


def _trim_scope(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    max_nodes: int,
    max_edges: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, list[dict[str, Any]]]:
    """Apply deterministic scope budgets without deleting control structure."""

    diagnostics: list[dict[str, Any]] = []
    omitted = 0
    working_nodes = list(nodes)
    working_edges = list(edges)
    priority = {
        "entry": 0,
        "exit": 0,
        "branch": 1,
        "multi_branch": 1,
        "loop": 1,
        "break": 1,
        "continue": 1,
        "return": 1,
        "dispatch": 2,
        "interface": 3,
        "free_function": 4,
    }
    while len(working_nodes) > max_nodes:
        candidates = [
            node
            for node in working_nodes
            if node.get("kind") not in _SCOPE_CONTROL_KINDS
        ]
        candidates.sort(
            key=lambda node: (
                priority.get(str(node.get("kind") or ""), 5),
                -int(node.get("order", 0) or 0),
            ),
            reverse=True,
        )
        removed = False
        for candidate in candidates:
            contracted = _contract_scope_node(
                str(candidate.get("id") or ""), working_nodes, working_edges
            )
            if contracted is None:
                continue
            working_nodes, working_edges = contracted
            omitted += 1
            removed = True
            break
        if not removed:
            break
    if len(working_nodes) > max_nodes:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "FLOW_SCOPE_NODE_BUDGET_EXCEEDED",
                "message": (
                    f"flow scope still contains {len(working_nodes)} nodes after compacting "
                    f"non-control steps; configured maxNodesPerScope={max_nodes}"
                ),
            }
        )
    if len(working_edges) > max_edges:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "FLOW_SCOPE_EDGE_BUDGET_EXCEEDED",
                "message": (
                    f"flow scope contains {len(working_edges)} edges; configured "
                    f"maxEdgesPerScope={max_edges}"
                ),
            }
        )
    if omitted:
        diagnostics.append(
            {
                "severity": "info",
                "code": "FLOW_SCOPE_NODE_BUDGET_COMPACTED",
                "message": f"compacted {omitted} non-control call steps to respect the scope node budget",
            }
        )
    return working_nodes, working_edges, omitted, diagnostics


def _scope_root_reason(
    *,
    node: dict[str, Any],
    target_id: str,
    target_ref: str,
    configured_roots: set[str],
    execution_only_ids: set[str],
    flow_module_id: str,
    auto_detect: bool,
) -> str | None:
    if target_id in configured_roots or target_ref in configured_roots:
        return "configured_root"
    if target_id in execution_only_ids:
        return "execution_only"
    if auto_detect and node.get("kind") == "interface" and node.get("moduleId") != flow_module_id:
        return "cross_module_capability"
    return None


def _build_flow_scopes(
    *,
    analysis: AnalysisResult,
    call_sites: list[CallSite],
    flow: dict[str, Any],
    resolver,
    module_meta: dict[str, dict[str, Any]],
    configured_roots: set[str],
    auto_detect: bool,
    max_scopes: int,
    max_nodes: int,
    max_edges: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build one-level interface scopes for a single bounded execution flow."""

    config = analysis.config.flow_scopes
    scopes: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    if not config.enabled:
        return scopes, diagnostics
    resolved_roots = {
        resolve_function_ref(analysis, None, ref)
        for ref in configured_roots
        if str(ref or "").strip()
    }
    resolved_roots.discard(None)
    seen_targets: set[str] = set()
    for node in flow.get("nodes", []):
        if len(scopes) >= max_scopes:
            diagnostics.append(
                {
                    "severity": "info",
                    "code": "FLOW_SCOPE_COUNT_BUDGET",
                    "message": f"flow {flow.get('id')} reached maxScopesPerFlow={max_scopes}",
                }
            )
            break
        if node.get("kind") not in {"free_function", "interface"}:
            continue
        target_id = str(node.get("targetFunctionId") or node.get("functionId") or "")
        target = analysis.function_by_id.get(target_id)
        if target is None or target.synthetic:
            continue
        if target_id == str(flow.get("entrypointId") or ""):
            continue
        target_ref = f"{target.module_name}:{target.qualname}"
        reason = _scope_root_reason(
            node=node,
            target_id=target_id,
            target_ref=target_ref,
            configured_roots=configured_roots,
            execution_only_ids=set(analysis.execution_only_function_ids),
            flow_module_id=str(flow.get("moduleId") or ""),
            auto_detect=auto_detect,
        )
        if reason is None:
            continue
        if target_id in seen_targets:
            continue
        seen_targets.add(target_id)
        scope_index = len(scopes) + 1
        digest = hashlib.sha1(f"{flow.get('id')}:{node.get('id')}:{target_id}".encode("utf-8")).hexdigest()[:10]
        scope_id = f"scope:{flow.get('id')}:{scope_index}:{digest}"
        scope_key = f"{flow.get('id')}:scope{scope_index}:{digest}"
        skeleton = build_entry_execution_skeleton(
            analysis,
            call_sites,
            target,
            flow_id=scope_id,
            flow_key=scope_key,
            resolve_target=resolver,
            module_meta=module_meta,
        )
        scope_nodes = list(skeleton.get("nodes") or [])
        scope_edges = list(skeleton.get("edges") or [])
        scope_nodes, scope_edges, omitted, budget_diagnostics = _trim_scope(
            scope_nodes,
            scope_edges,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        for scope_node in scope_nodes:
            scope_node["scopeId"] = scope_id
        helper_hints = _helper_interface_hints(
            analysis=analysis,
            call_sites=call_sites,
            resolver=resolver,
            nodes=scope_nodes,
            root_module_id=target.module_id,
        )
        interface_summary = _scope_interface_summary(scope_nodes, helper_hints)
        scope_diagnostics = [
            *list(skeleton.get("diagnostics") or []),
            *budget_diagnostics,
        ]
        if not interface_summary:
            scope_diagnostics.append(
                {
                    "severity": "info",
                    "code": "FLOW_SCOPE_NO_EXTERNAL_INTERFACE",
                    "message": (
                        f"scope {scope_id} contains no directly resolved external capability interface"
                    ),
                    "functionId": target_id,
                }
            )
        scope = {
            "kind": "archmap.execution-scope",
            "id": scope_id,
            "parentNodeId": node.get("id"),
            "rootFunctionId": target_id,
            "moduleId": target.module_id,
            "depth": 1,
            "entrypointId": target_id,
            "name": f"{target.name}() 接口",
            "nodes": scope_nodes,
            "edges": scope_edges,
            "layout": layout_execution_flow(
                scope_nodes,
                scope_edges,
                scope_id,
            ),
            "nodeCount": len(scope_nodes),
            "edgeCount": len(scope_edges),
            "truncated": bool(omitted) or any(
                item.get("code") in {
                    "FLOW_SCOPE_NODE_BUDGET_EXCEEDED",
                    "FLOW_SCOPE_EDGE_BUDGET_EXCEEDED",
                }
                for item in scope_diagnostics
            ),
            "omittedNodeCount": omitted,
            "diagnostics": scope_diagnostics,
            "interfaceSummary": interface_summary,
        }
        scopes.append(scope)
        node["drilldown"] = {
            "status": "available",
            "scopeId": scope_id,
            "reason": reason,
            "interfaceSummary": interface_summary,
        }
        diagnostics.extend(scope_diagnostics)
    unresolved_roots = sorted(
        str(ref) for ref in configured_roots
        if str(ref or "").strip() and resolve_function_ref(analysis, None, str(ref)) is None
    )
    for ref in unresolved_roots:
        diagnostics.append(
            {
                "severity": "warning",
                "code": "FLOW_SCOPE_ROOT_UNRESOLVED",
                "message": f"flowScopes root {ref!r} did not match a project callable",
            }
        )
    return scopes, diagnostics


def build_execution_flows(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    entrypoints: list[dict[str, Any]],
    module_graphs: list[dict[str, Any]],
    contract_model: ContractModel | None = None,
    dispatch_hints: list[DispatchHint] | None = None,
) -> tuple[list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    """Build bounded execution flows for every entrypoint."""

    del contract_model  # capability facts are already projected into module graphs
    call_list = list(call_sites)
    module_meta = _module_meta(module_graphs)
    capability_by_function, capability_by_constructor, _ = _capability_indexes(module_graphs)
    diagnostics: list[dict[str, Any]] = []
    dispatch_resolver = DispatchResolver(
        analysis=analysis,
        call_sites=call_list,
        hints=dispatch_hints,
        diagnostics=diagnostics,
    )
    resolver = _build_target_resolver(
        analysis=analysis,
        module_meta=module_meta,
        capability_by_function=capability_by_function,
        capability_by_constructor=capability_by_constructor,
        dispatch_resolver=dispatch_resolver,
    )
    flows: list[dict[str, Any]] = []
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
        skeleton["nodeCount"] = len(skeleton.get("nodes") or [])
        skeleton["edgeCount"] = len(skeleton.get("edges") or [])
        scopes, scope_diagnostics = _build_flow_scopes(
            analysis=analysis,
            call_sites=call_list,
            flow=skeleton,
            resolver=resolver,
            module_meta=module_meta,
            configured_roots=set(analysis.config.flow_scopes.roots),
            auto_detect=analysis.config.flow_scopes.auto_detect,
            max_scopes=analysis.config.flow_scopes.max_scopes_per_flow,
            max_nodes=analysis.config.flow_scopes.max_nodes_per_scope,
            max_edges=analysis.config.flow_scopes.max_edges_per_scope,
        )
        skeleton["scopes"] = scopes
        skeleton["layout"] = layout_execution_flow(
            list(skeleton.get("nodes") or []),
            list(skeleton.get("edges") or []),
            flow_id,
        )
        # Scope-local compaction and simplification diagnostics stay attached
        # to the scope.  Only actionable project-level warning/error records
        # are promoted into bundle diagnostics.
        diagnostics.extend(
            item for item in scope_diagnostics
            if item.get("severity") in {"warning", "error"}
        )
        flows.append(skeleton)
        diagnostics.extend(skeleton.get("diagnostics") or [])
        if primary_id is None:
            primary_id = flow_id
    return flows, primary_id, diagnostics
