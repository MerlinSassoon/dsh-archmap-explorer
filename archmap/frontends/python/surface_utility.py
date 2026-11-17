"""User-surface detection and propagation for the Python frontend.

Surfaces are a projection over entrypoint reachability and explicit IO/event
primitives.  They are deliberately separate from developer API exposure and
never inferred from project-specific function names.
"""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from typing import Any, Iterable

from ...model.analysis_model import AnalysisResult, FunctionInfo, ModuleInfo
from ...model.call_model import CallSite
from ...model.contract_model import ProviderRoleInfo
from ...utility.call_utility import _calls_in_function, _unparse


_PRIMITIVE_KINDS = {
    "cli_input",
    "cli_output",
    "file_io",
    "network_endpoint",
    "network_client",
    "keyboard_event",
}


def _surface_label(kind: str, fn: FunctionInfo) -> str:
    return {
        "cli_input": f"CLI 输入 · {fn.name}()",
        "cli_output": f"CLI 输出 · {fn.name}()",
        "file_io": f"文件 IO · {fn.name}()",
        "network_endpoint": f"网络监听 · {fn.name}()",
        "network_client": f"网络连接 · {fn.name}()",
        "keyboard_event": f"键盘事件 · {fn.name}()",
    }.get(kind, f"{kind} · {fn.name}()")


def _call_kind(call_text: str) -> str | None:
    text = str(call_text or "")
    tail = text.split(".")[-1].split("(")[0]
    if tail == "input":
        return "cli_input"
    if tail == "print":
        return "cli_output"
    if tail == "open":
        return "file_io"
    if tail in {"read_text", "write_text", "read_bytes", "write_bytes", "readline", "writelines"}:
        return "file_io"
    if "stdout" in text or "stderr" in text:
        return "cli_output"
    if tail in {"bind", "listen", "accept", "serve_forever"}:
        return "network_endpoint"
    if tail in {"connect", "send", "sendall", "recv", "recvfrom"}:
        return "network_client"
    if "keyboard.listener" in text.lower() or "keyboard.listener" in text.lower():
        return "keyboard_event"
    if ".listener" in text.lower() and ("keyboard" in text.lower() or "event" in text.lower()):
        return "keyboard_event"
    return None


def _detect_primitives(analysis: AnalysisResult) -> dict[str, set[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for fn in analysis.functions:
        for call in _calls_in_function(fn):
            text = _unparse(call.func, 240)
            kind = _call_kind(text)
            if kind:
                found[fn.id].add(kind)
    return found


def _reachable_from_entrypoints(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    entrypoints: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, bool]]:
    """Return primitive function -> entrypoint ids, and polymorphic path flags."""

    outgoing: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for site in call_sites:
        if site.to_function_id:
            outgoing[site.from_function_id].append((site.to_function_id, False))
        if site.polymorphic:
            for candidate in site.candidates:
                outgoing[site.from_function_id].append((candidate, True))

    reachable_by: dict[str, set[str]] = defaultdict(set)
    polymorphic_by: dict[str, bool] = defaultdict(bool)
    for entry in entrypoints:
        start = str(entry.get("functionId") or "")
        if start not in analysis.function_by_id:
            continue
        queue: deque[tuple[str, bool]] = deque([(start, False)])
        seen: dict[str, bool] = {start: False}
        while queue:
            function_id, poly = queue.popleft()
            reachable_by[function_id].add(start)
            polymorphic_by[function_id] = polymorphic_by[function_id] or poly
            for target, edge_poly in outgoing.get(function_id, []):
                next_poly = poly or edge_poly
                if target not in seen:
                    seen[target] = next_poly
                    queue.append((target, next_poly))
                elif next_poly and not seen[target]:
                    seen[target] = True
                    queue.append((target, True))
    return reachable_by, polymorphic_by


def _resolve_function_ref(analysis: AnalysisResult, value: str) -> FunctionInfo | None:
    value = str(value or "").strip()
    if not value:
        return None
    if value in analysis.function_by_id:
        return analysis.function_by_id[value]
    if ":" in value:
        module_name, name = value.rsplit(":", 1)
        matches = [
            fn for fn in analysis.functions
            if (fn.module_name == module_name or fn.module_name.endswith("." + module_name))
            and (fn.name == name or fn.qualname == name)
        ]
    else:
        matches = [
            fn for fn in analysis.functions
            if fn.name == value or fn.qualname == value
        ]
    return matches[0] if len(matches) == 1 else None


def build_user_surfaces(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite],
    entrypoints: list[dict[str, Any]],
    provider_roles: dict[str, ProviderRoleInfo],
) -> list[dict[str, Any]]:
    """Build canonical user-surface records with evidence and confidence."""

    call_list = list(call_sites)
    primitive_by_function = _detect_primitives(analysis)
    reachable_by, polymorphic_by = _reachable_from_entrypoints(analysis, call_list, entrypoints)
    surfaces: list[dict[str, Any]] = []

    for function_id, kinds in sorted(primitive_by_function.items()):
        fn = analysis.function_by_id.get(function_id)
        if fn is None:
            continue
        provider_id = (
            f"cls:{fn.module_name}.{fn.class_name}"
            if fn.class_name
            else fn.id
        )
        if entrypoints and not reachable_by.get(fn.id):
            continue
        role_info = provider_roles.get(provider_id)
        for kind in sorted(kinds):
            surfaces.append(
                {
                    "id": f"surface:{kind}:{function_id}",
                    "kind": kind,
                    "display": _surface_label(kind, fn),
                    "audiences": ["end_user"],
                    "moduleId": fn.module_id,
                    "providerId": provider_id,
                    "providerRole": role_info.role if role_info else None,
                    "evidenceFunctionIds": [fn.id],
                    "propagatedFunctionIds": [fn.id],
                    "entrypointIds": sorted(reachable_by.get(fn.id, set())),
                    "confidence": "medium" if polymorphic_by.get(fn.id) else "high",
                    "source": "io_primitive",
                }
            )

    for override in analysis.config.user_surface_overrides:
        fn = _resolve_function_ref(analysis, str(override.get("function") or ""))
        if fn is None:
            continue
        kind = str(override.get("kind") or "cli_input")
        provider_id = f"cls:{fn.module_name}.{fn.class_name}" if fn.class_name else fn.id
        role_info = provider_roles.get(provider_id)
        surfaces.append(
            {
                "id": f"surface:{kind}:{fn.id}:config",
                "kind": kind,
                "display": override.get("display") or _surface_label(kind, fn),
                "audiences": list(override.get("audiences") or ["end_user"]),
                "moduleId": fn.module_id,
                "providerId": provider_id,
                "providerRole": role_info.role if role_info else None,
                "evidenceFunctionIds": [fn.id],
                "propagatedFunctionIds": [fn.id],
                "entrypointIds": sorted(reachable_by.get(fn.id, set())),
                "confidence": override.get("confidence") or "high",
                "source": "config",
            }
        )

    unique: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        unique.setdefault(str(surface["id"]), surface)
    return sorted(unique.values(), key=lambda item: (item["moduleId"], item["kind"], item["id"]))
