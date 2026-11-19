"""Read-only impact, trace and DSM queries over an ArchMap bundle.

P4 query results are intentionally not persisted into the architecture bundle:
they depend on query parameters and can grow combinatorially.  The bundle
remains the canonical static fact layer.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any, Iterable


def _detail_map(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in bundle.get("functionDetails", [])}


def _capability_map(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(api.get("id")): api
        for graph in bundle.get("moduleGraphs", [])
        for api in graph.get("providedApis", [])
    }


def _relation_key(relation: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(relation.get("fromClassId")),
        str(relation.get("kind")),
        str(relation.get("toClassId")),
        str(relation.get("moduleId")),
    )


def _semantic_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_functions = _detail_map(before)
    after_functions = _detail_map(after)
    before_apis = _capability_map(before)
    after_apis = _capability_map(after)
    before_relations = {
        _relation_key(item): item for item in before.get("projectGraph", {}).get("typeRelations", [])
    }
    after_relations = {
        _relation_key(item): item for item in after.get("projectGraph", {}).get("typeRelations", [])
    }
    before_surfaces = {
        str(item.get("id")): item for item in before.get("projectGraph", {}).get("userSurfaces", [])
    }
    after_surfaces = {
        str(item.get("id")): item for item in after.get("projectGraph", {}).get("userSurfaces", [])
    }

    function_fields = (
        "signature",
        "sourceHash",
        "note",
        "apiExposure",
        "apiExposureSource",
        "ownerClassId",
        "isAbstract",
        "returns",
        "raises",
    )
    changed_functions: list[dict[str, Any]] = []
    for function_id in sorted(set(before_functions) | set(after_functions)):
        old = before_functions.get(function_id)
        new = after_functions.get(function_id)
        if old is None or new is None:
            changed_functions.append(
                {"functionId": function_id, "change": "added" if old is None else "removed"}
            )
            continue
        changed = [field for field in function_fields if old.get(field) != new.get(field)]
        if changed:
            changed_functions.append({"functionId": function_id, "change": "changed", "fields": changed})

    api_fields = (
        "kind",
        "signature",
        "providerId",
        "providerRole",
        "exposure",
        "exposureSource",
        "functionId",
        "inherited",
        "declaredInProviderId",
        "overridesCapabilityId",
    )
    changed_apis: list[dict[str, Any]] = []
    for api_id in sorted(set(before_apis) | set(after_apis)):
        old = before_apis.get(api_id)
        new = after_apis.get(api_id)
        if old is None or new is None:
            changed_apis.append({"apiId": api_id, "change": "added" if old is None else "removed"})
            continue
        changed = [field for field in api_fields if old.get(field) != new.get(field)]
        if changed:
            changed_apis.append({"apiId": api_id, "change": "changed", "fields": changed})

    added_relations = [
        after_relations[key] for key in sorted(set(after_relations) - set(before_relations))
    ]
    removed_relations = [
        before_relations[key] for key in sorted(set(before_relations) - set(after_relations))
    ]
    added_surfaces = [
        after_surfaces[key] for key in sorted(set(after_surfaces) - set(before_surfaces))
    ]
    removed_surfaces = [
        before_surfaces[key] for key in sorted(set(before_surfaces) - set(after_surfaces))
    ]
    return {
        "functions": changed_functions,
        "apis": changed_apis,
        "typeRelations": {
            "added": added_relations,
            "removed": removed_relations,
        },
        "userSurfaces": {
            "added": added_surfaces,
            "removed": removed_surfaces,
        },
    }


def _build_reverse_indexes(bundle: dict[str, Any]) -> tuple[
    dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]
]:
    callers_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for site in bundle.get("callSites", []):
        targets: list[str] = []
        if site.get("toFunctionId"):
            targets.append(str(site["toFunctionId"]))
        if site.get("polymorphic"):
            targets.extend(str(item) for item in site.get("candidates", []))
        for target in targets:
            callers_by_target[target].append(site)

    rel_sources_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relation in bundle.get("projectGraph", {}).get("typeRelations", []):
        rel_sources_by_target[str(relation.get("toClassId"))].append(relation)
    return callers_by_target, rel_sources_by_target


def _function_owner_map(bundle: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("id")): str(item.get("ownerClassId"))
        for item in bundle.get("functionDetails", [])
        if item.get("ownerClassId")
    }


def build_impact(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    max_depth: int = 6,
    max_nodes: int = 200,
) -> dict[str, Any]:
    """Compute reverse impact from semantic changes between two bundles."""

    changes = _semantic_changes(before, after)
    details = {**_detail_map(before), **_detail_map(after)}
    owner_by_function = _function_owner_map(after) | _function_owner_map(before)
    seed_records: list[dict[str, Any]] = []
    for item in changes["functions"]:
        fn_id = item["functionId"]
        detail = details.get(fn_id, {})
        seed_records.append(
            {
                "nodeId": fn_id,
                "nodeKind": "function",
                "label": detail.get("qualifiedName") or fn_id,
                "change": item["change"],
                "fields": item.get("fields", []),
            }
        )
        if fn_id in owner_by_function:
            seed_records.append(
                {
                    "nodeId": owner_by_function[fn_id],
                    "nodeKind": "provider",
                    "label": owner_by_function[fn_id],
                    "change": "owner_of_changed_function",
                }
            )
    for item in changes["apis"]:
        api_id = item["apiId"]
        api = (_capability_map(after).get(api_id) or _capability_map(before).get(api_id) or {})
        seed_records.append(
            {
                "nodeId": api_id,
                "nodeKind": "api",
                "label": api.get("display") or api_id,
                "change": item["change"],
                "fields": item.get("fields", []),
            }
        )
    for relation in changes["typeRelations"]["added"] + changes["typeRelations"]["removed"]:
        seed_records.append(
            {
                "nodeId": str(relation.get("fromClassId")),
                "nodeKind": "provider",
                "label": str(relation.get("fromClassId")),
                "change": "type_relation_changed",
            }
        )
    for surface in changes["userSurfaces"]["added"] + changes["userSurfaces"]["removed"]:
        seed_records.append(
            {
                "nodeId": str(surface.get("id")),
                "nodeKind": "surface",
                "label": surface.get("display") or surface.get("id"),
                "change": "user_surface_changed",
            }
        )

    callers_by_target, rel_sources_by_target = _build_reverse_indexes(after)
    # Include removed callers as impact evidence when present.
    before_callers, before_relations = _build_reverse_indexes(before)
    for key, values in before_callers.items():
        callers_by_target.setdefault(key, []).extend(values)
    for key, values in before_relations.items():
        rel_sources_by_target.setdefault(key, []).extend(values)

    impacts: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, str, int, list[str], str]] = deque()
    for seed in seed_records:
        node_id = seed["nodeId"]
        if node_id in impacts:
            continue
        record = {
            **seed,
            "severity": "high" if seed["nodeKind"] in {"api", "surface"} else "medium",
            "confidence": "high",
            "path": [node_id],
            "evidence": [],
        }
        impacts[node_id] = record
        queue.append((node_id, seed["nodeKind"], 0, [node_id], "high"))

    truncated = False
    while queue:
        node_id, node_kind, depth, path, confidence = queue.popleft()
        if depth >= max_depth:
            continue
        if len(impacts) >= max_nodes:
            truncated = True
            break

        candidates: list[tuple[str, str, str, dict[str, Any]]] = []
        for site in callers_by_target.get(node_id, []):
            caller_id = str(site.get("fromFunctionId"))
            candidate_confidence = "low" if site.get("polymorphic") else str(site.get("confidence") or "medium")
            candidates.append((caller_id, "function", "caller", site))
        for relation in rel_sources_by_target.get(node_id, []):
            source_id = str(relation.get("fromClassId"))
            candidates.append(
                (source_id, "provider", f"reverse_{relation.get('kind')}", relation)
            )
        if node_kind == "function" and node_id in owner_by_function:
            owner_id = owner_by_function[node_id]
            candidates.append((owner_id, "provider", "owner", {"ownerClassId": owner_id}))
        if node_kind == "api":
            api = _capability_map(after).get(node_id, {})
            function_id = api.get("functionId")
            if function_id:
                candidates.append((str(function_id), "function", "api_implementation", {"apiId": node_id}))

        for candidate_id, candidate_kind, relation_kind, evidence in candidates:
            if candidate_id in impacts:
                continue
            new_path = [*path, candidate_id]
            record = {
                "nodeId": candidate_id,
                "nodeKind": candidate_kind,
                "label": candidate_id,
                "change": relation_kind,
                "severity": "medium" if relation_kind == "caller" else "low",
                "confidence": confidence if confidence == "low" else ("low" if relation_kind == "caller" and evidence.get("polymorphic") else "medium"),
                "path": new_path,
                "evidence": [evidence],
            }
            impacts[candidate_id] = record
            queue.append(
                (
                    candidate_id,
                    candidate_kind,
                    depth + 1,
                    new_path,
                    "low" if evidence.get("polymorphic") else record["confidence"],
                )
            )
            if len(impacts) >= max_nodes:
                truncated = True
                break
        if truncated:
            break

    summary_kinds = Counter(item["nodeKind"] for item in impacts.values())
    return {
        "kind": "archmap.impact",
        "beforeFingerprint": before.get("project", {}).get("fingerprint"),
        "afterFingerprint": after.get("project", {}).get("fingerprint"),
        "changes": changes,
        "seeds": seed_records,
        "impacts": sorted(impacts.values(), key=lambda item: (item["nodeKind"], item["nodeId"])),
        "summary": {
            "functions": summary_kinds.get("function", 0),
            "providers": summary_kinds.get("provider", 0),
            "apis": summary_kinds.get("api", 0),
            "surfaces": summary_kinds.get("surface", 0),
            "total": len(impacts),
        },
        "truncated": truncated,
    }


def _resolve_trace_start(bundle: dict[str, Any], start: str) -> str | None:
    details = _detail_map(bundle)
    if start in details:
        return start
    apis = _capability_map(bundle)
    if start in apis:
        return apis[start].get("functionId")
    class_ids = {
        str(node.get("id"))
        for graph in bundle.get("moduleGraphs", [])
        for node in graph.get("nodes", [])
        if node.get("kind") == "class"
    }
    if start in class_ids:
        return start
    matches = [
        function_id
        for function_id, detail in details.items()
        if detail.get("name") == start
        or detail.get("qualifiedName") == start
        or str(detail.get("qualifiedName", "")).endswith("." + start)
    ]
    return matches[0] if len(matches) == 1 else None


def _function_visibility_map(bundle: dict[str, Any]) -> dict[str, str]:
    visibility: dict[str, str] = {}
    for graph in bundle.get("moduleGraphs", []):
        for node in graph.get("nodes", []):
            if node.get("kind") == "class":
                for method in node.get("methods", []):
                    visibility[str(method.get("id"))] = str(node.get("providerVisibility") or "internal")
            elif node.get("kind") == "function":
                visibility[str(node.get("id"))] = str(node.get("providerVisibility") or "internal")
    return visibility


def _trace_edges(bundle: dict[str, Any], include_internal: bool) -> dict[str, list[dict[str, Any]]]:
    visibility = _function_visibility_map(bundle)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for site in bundle.get("callSites", []):
        source = str(site.get("fromFunctionId"))
        if site.get("toFunctionId"):
            target = str(site["toFunctionId"])
            if include_internal or visibility.get(target, "public") == "public":
                outgoing[source].append(
                    {
                        "from": source,
                        "to": target,
                        "kind": "call",
                        "confidence": site.get("confidence", "medium"),
                        "callSiteId": site.get("id"),
                        "line": site.get("line"),
                    }
                )
        if site.get("polymorphic"):
            for candidate in site.get("candidates", []):
                if include_internal or visibility.get(str(candidate), "public") == "public":
                    outgoing[source].append(
                        {
                            "from": source,
                            "to": str(candidate),
                            "kind": "polymorphic_candidate",
                            "confidence": "medium",
                            "callSiteId": site.get("id"),
                            "line": site.get("line"),
                        }
                    )
    return outgoing


def _callee_tail(callee_text: str) -> str:
    """Return a best-effort callable name from an unresolved callee expression."""

    text = str(callee_text or "").strip().split("(", 1)[0].strip()
    return text.rsplit(".", 1)[-1] if text else ""


def _unresolved_trace_references(
    bundle: dict[str, Any],
    start_id: str,
    *,
    direction: str,
    max_items: int = 50,
) -> tuple[list[dict[str, Any]], bool]:
    """Expose unresolved call sites that may concern the trace start.

    These are intentionally low-confidence hints, not call edges. They prevent a
    failed resolution from being presented as a definitive zero-caller answer.
    """

    detail = _detail_map(bundle).get(start_id) or {}
    start_name = str(detail.get("name") or "")
    references: list[dict[str, Any]] = []
    for site in bundle.get("callSites", []):
        if site.get("resolved") or site.get("external"):
            continue
        from_id = str(site.get("fromFunctionId") or "")
        callee_text = str(site.get("calleeText") or "")
        matches_start = bool(start_name) and _callee_tail(callee_text) == start_name
        if direction == "inbound":
            if not matches_start or from_id == start_id:
                continue
        elif direction == "outbound":
            if from_id != start_id:
                continue
        else:
            continue
        references.append(
            {
                "callSiteId": site.get("id"),
                "fromFunctionId": from_id,
                "toFunctionId": site.get("toFunctionId"),
                "file": site.get("file"),
                "line": site.get("line"),
                "column": site.get("column"),
                "calleeText": callee_text,
                "callText": site.get("callText"),
                "confidence": "low",
                "reason": "callee-name-match" if direction == "inbound" else "unresolved-call",
            }
        )
    return references[:max_items], len(references) > max_items


def build_trace(
    bundle: dict[str, Any],
    start: str,
    *,
    direction: str = "outbound",
    max_depth: int = 8,
    max_nodes: int = 200,
    include_internal: bool = True,
) -> dict[str, Any]:
    """Trace static and polymorphic call paths from/to one function."""

    resolved = _resolve_trace_start(bundle, start)
    if resolved is None:
        raise ValueError(f"trace start not found: {start}")
    unresolved_references, unresolved_truncated = _unresolved_trace_references(
        bundle, resolved, direction=direction
    )
    outgoing = _trace_edges(bundle, include_internal)
    if direction == "inbound":
        reverse: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for source, edges in outgoing.items():
            for edge in edges:
                reverse[edge["to"]].append(
                    {
                        **edge,
                        "from": edge["to"],
                        "to": source,
                    }
                )
        outgoing = reverse

    paths: list[dict[str, Any]] = []
    visited: dict[str, int] = {resolved: 0}
    queue: deque[tuple[str, list[dict[str, Any]], int]] = deque([(resolved, [], 0)])
    truncated = False
    while queue:
        node_id, path, depth = queue.popleft()
        if depth >= max_depth:
            continue
        edges = outgoing.get(node_id, [])
        for edge in edges:
            target = edge["to"]
            next_path = [*path, edge]
            paths.append(
                {
                    "from": resolved,
                    "to": target,
                    "depth": depth + 1,
                    "nodes": [resolved, *[item["to"] for item in next_path]],
                    "edges": next_path,
                    "confidence": "low"
                    if any(item["kind"] == "polymorphic_candidate" for item in next_path)
                    else "high",
                }
            )
            if target not in visited or depth + 1 < visited[target]:
                visited[target] = depth + 1
                queue.append((target, next_path, depth + 1))
            if len(paths) >= max_nodes:
                truncated = True
                break
        if truncated:
            break
    return {
        "kind": "archmap.trace",
        "direction": direction,
        "startId": resolved,
        "maxDepth": max_depth,
        "nodes": [
            {"nodeId": node_id, "depth": depth}
            for node_id, depth in sorted(visited.items(), key=lambda item: (item[1], item[0]))
        ],
        "paths": paths,
        "unresolvedReferences": unresolved_references,
        "unresolvedCount": len(unresolved_references),
        "unresolvedTruncated": unresolved_truncated,
        "truncated": truncated,
    }


def build_dsm(
    bundle: dict[str, Any], *, level: str = "module", include_internal: bool = True
) -> dict[str, Any]:
    """Build a module or provider dependency-structure matrix."""

    if level not in {"module", "provider"}:
        raise ValueError("DSM level must be module or provider")
    provider_roles = {
        str(node.get("id")): {
            "role": node.get("providerRole"),
            "visibility": node.get("providerVisibility"),
            "moduleId": graph.get("moduleId"),
        }
        for graph in bundle.get("moduleGraphs", [])
        for node in graph.get("nodes", [])
        if node.get("kind") in {"class", "function"}
    }
    owner_by_function: dict[str, str] = {}
    for detail in bundle.get("functionDetails", []):
        function_id = str(detail.get("id"))
        owner = detail.get("ownerClassId")
        owner_by_function[function_id] = str(owner) if owner else function_id

    matrix: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))

    def add(source: str, target: str, kind: str, weight: int = 1) -> None:
        if not source or not target or source == target:
            return
        item = matrix[source].setdefault(target, {"count": 0, "kinds": {}})
        item["count"] += weight
        item["kinds"][kind] = item["kinds"].get(kind, 0) + weight

    if level == "module":
        for edge in bundle.get("projectGraph", {}).get("edges", []):
            add(str(edge.get("from")), str(edge.get("to")), str(edge.get("primaryType") or "call"))
        for relation in bundle.get("projectGraph", {}).get("typeRelations", []):
            source = str(relation.get("moduleId"))
            target = str(relation.get("targetModuleId"))
            add(source, target, str(relation.get("kind") or "relation"))
    else:
        for site in bundle.get("callSites", []):
            if not site.get("resolved") or not site.get("toFunctionId"):
                continue
            source = owner_by_function.get(str(site.get("fromFunctionId")), str(site.get("fromFunctionId")))
            target = owner_by_function.get(str(site.get("toFunctionId")), str(site.get("toFunctionId")))
            if not include_internal:
                if provider_roles.get(source, {}).get("visibility") != "public":
                    continue
                if provider_roles.get(target, {}).get("visibility") != "public":
                    continue
            add(source, target, str(site.get("kind") or "call"))
        for relation in bundle.get("projectGraph", {}).get("typeRelations", []):
            source = str(relation.get("fromProviderId") or relation.get("fromClassId"))
            target = str(relation.get("toProviderId") or relation.get("toClassId"))
            if not include_internal:
                if provider_roles.get(source, {}).get("visibility") != "public":
                    continue
                if provider_roles.get(target, {}).get("visibility") != "public":
                    continue
            add(source, target, str(relation.get("kind") or "relation"))

    nodes = sorted(
        set(provider_roles) if level == "provider" else {
            str(module.get("id")) for module in bundle.get("projectGraph", {}).get("modules", [])
        }
    )
    return {
        "kind": "archmap.dsm",
        "level": level,
        "nodes": nodes,
        "matrix": {
            source: {
                target: {
                    **payload,
                    "kinds": dict(sorted(payload["kinds"].items())),
                }
                for target, payload in sorted(targets.items())
            }
            for source, targets in sorted(matrix.items())
        },
        "stats": {
            "nodes": len(nodes),
            "edges": sum(len(targets) for targets in matrix.values()),
        },
    }
