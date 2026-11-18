"""Shared static call-target and dynamic-dispatch resolution.

The execution flow and the legacy main-flow projection must agree on how a
dynamic call site is resolved.  This utility owns that single source of truth:
function-reference resolution, dispatch hints, inline comments, argparse
registries, static handler tables and polymorphic candidates.
"""

from __future__ import annotations

import ast
import re
import shlex
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..config.project_config import DispatchHint
from ..model.analysis_model import AnalysisResult, FunctionInfo, ModuleInfo
from ..model.call_model import CallSite

_DISPATCH_COMMENT = re.compile(r"#\s*archmap:dispatch\b(?P<body>.*)$", re.IGNORECASE)


def module_from_name(analysis: AnalysisResult, module_name: str) -> ModuleInfo | None:
    """Resolve a dotted module or file-like name to one analyzed module."""

    if not module_name:
        return None
    name = module_name.removesuffix(".py").replace("/", ".")
    direct = next((module for module in analysis.modules if module.name == name), None)
    if direct is not None:
        return direct
    tail = name.split(".")[-1]
    matches = [module for module in analysis.modules if module.name.split(".")[-1] == tail]
    return matches[0] if len(matches) == 1 else None


def resolve_function_ref(
    analysis: AnalysisResult,
    current_module: ModuleInfo | None,
    ref: str,
) -> str | None:
    """Resolve a configured function reference to a canonical function id."""

    value = str(ref or "").strip()
    if not value:
        return None
    if value.startswith("fn:"):
        return value if value in analysis.function_by_id else None
    if ":" in value:
        module_part, name = value.rsplit(":", 1)
        module = module_from_name(analysis, module_part)
        if module is not None:
            fn = module.functions.get(name)
            if fn is not None:
                return fn.id
            matches = [item for item in module.functions.values() if item.name == name]
            if len(matches) == 1:
                return matches[0].id
    if "." in value:
        module_part, name = value.rsplit(".", 1)
        module = module_from_name(analysis, module_part)
        if module is not None:
            fn = module.functions.get(name)
            if fn is not None:
                return fn.id
    if current_module is not None:
        fn = current_module.functions.get(value)
        if fn is not None:
            return fn.id
        imported = current_module.imports.get(value)
        if imported is not None:
            target = module_from_name(analysis, imported.module)
            if target is not None:
                fn = target.functions.get(imported.name or value)
                if fn is not None:
                    return fn.id
    matches = [fn.id for fn in analysis.functions if fn.name == value or fn.qualname == value]
    return matches[0] if len(matches) == 1 else None


def parse_dispatch_comment(text: str) -> dict[str, Any] | None:
    """Parse one inline ``# archmap:dispatch`` declaration."""

    match = _DISPATCH_COMMENT.search(text or "")
    if not match:
        return None
    body = match.group("body").strip()
    tokens = shlex.split(body) if body else []
    candidates: list[str] = []
    complete = False
    reason = "comment"
    for token in tokens:
        if token.startswith("candidates="):
            candidates.extend(
                item.strip()
                for item in token.removeprefix("candidates=").split(",")
                if item.strip()
            )
        elif token.startswith("complete="):
            complete = token.removeprefix("complete=").strip().lower() == "true"
        elif token.startswith("reason="):
            reason = token.removeprefix("reason=").strip() or reason
    return {
        "candidates": candidates,
        "complete": complete,
        "reason": reason,
        "source": "comment",
    }


def description_comment(source_lines: list[str], line: int) -> str:
    """Find a dispatch declaration on or immediately above one call line."""

    for index in (line, line - 1, line - 2):
        if 1 <= index <= len(source_lines):
            text = source_lines[index - 1]
            if _DISPATCH_COMMENT.search(text):
                return text
    return ""


def is_dynamic_dispatch_site(site: CallSite) -> bool:
    """Return whether an unresolved call site is a dynamic callable dispatch."""

    if site.resolved or site.external:
        return False
    text = str(site.callee_text or "").strip()
    if text.endswith(".func"):
        return True
    if text.startswith("getattr("):
        return True
    # Calling the result of a mapping lookup, e.g. HANDLERS[command]().
    # Attribute access on a subscript (detail['id'].replace) is not a
    # dynamic callable dispatch and must not create a dispatch node.
    if text.endswith("]") and "[" in text and "]." not in text:
        return True
    return False


def _static_dispatch_candidates(
    analysis: AnalysisResult,
) -> tuple[list[str], dict[str, dict[str, list[str]]]]:
    """Discover high-signal argparse and static-registry candidates."""

    argparse_candidates: list[str] = []
    registry_candidates: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for module in analysis.modules:
        for fn in module.functions.values():
            for node in ast.walk(fn.node):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr == "set_defaults":
                        for keyword in node.keywords:
                            if keyword.arg != "func":
                                continue
                            ref = None
                            if isinstance(keyword.value, ast.Name):
                                ref = keyword.value.id
                            elif isinstance(keyword.value, ast.Attribute):
                                ref = keyword.value.attr
                            resolved = resolve_function_ref(analysis, module, ref or "")
                            if resolved:
                                argparse_candidates.append(resolved)
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target = node.targets[0].id
                    values: list[ast.AST] = []
                    if isinstance(node.value, ast.Dict):
                        values = [value for value in node.value.values if value is not None]
                    elif isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        values = list(node.value.elts)
                    for value in values:
                        ref = None
                        if isinstance(value, ast.Name):
                            ref = value.id
                        elif isinstance(value, ast.Attribute):
                            ref = value.attr
                        resolved = resolve_function_ref(analysis, module, ref or "")
                        if resolved:
                            registry_candidates[module.name][target].append(resolved)
    return (
        sorted(set(argparse_candidates)),
        {
            module: {name: sorted(set(values)) for name, values in tables.items()}
            for module, tables in registry_candidates.items()
        },
    )


@dataclass
class DispatchResolution:
    """Canonical result of resolving one dynamic dispatch call site."""

    candidates: list[str] = field(default_factory=list)
    candidate_set_complete: bool = False
    candidate_source: str = "unknown"
    reason: str = "dynamic_dispatch"
    unresolved_reason: str | None = "dynamic_callable_not_inferable"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates": list(self.candidates),
            "candidateCount": len(self.candidates),
            "candidateSetComplete": self.candidate_set_complete,
            "candidateSource": self.candidate_source,
            "reason": self.reason,
            "unresolvedReason": self.unresolved_reason,
        }


class DispatchResolver:
    """Resolve dynamic dispatch sites once for all flow projections.

    The resolver computes the occurrence order from the supplied call-site
    facts, so configured hints can target the first, second, etc. dynamic call
    for a function without each projection reimplementing that logic.
    """

    def __init__(
        self,
        *,
        analysis: AnalysisResult,
        call_sites: Iterable[CallSite],
        hints: list[DispatchHint] | None,
        diagnostics: list[dict[str, Any]],
    ) -> None:
        self.analysis = analysis
        self.hints = list(hints or [])
        self.diagnostics = diagnostics
        self.argparse_candidates, self.registry_candidates = _static_dispatch_candidates(analysis)
        self._occurrence_by_call_site: dict[str, int] = {}
        grouped: dict[str, list[CallSite]] = defaultdict(list)
        for site in call_sites:
            if site.polymorphic or is_dynamic_dispatch_site(site):
                grouped[site.from_function_id].append(site)
        for sites in grouped.values():
            sites.sort(key=lambda item: (item.line, item.column, item.id))
            for index, site in enumerate(sites, start=1):
                self._occurrence_by_call_site[site.id] = index

    def _resolve_candidates(
        self,
        analysis: AnalysisResult,
        module: ModuleInfo | None,
        candidates: list[str],
        *,
        expression: str,
    ) -> list[str]:
        resolved: list[str] = []
        for candidate in candidates:
            function_id = resolve_function_ref(analysis, module, candidate)
            if function_id:
                resolved.append(function_id)
            else:
                self.diagnostics.append(
                    {
                        "severity": "warning",
                        "code": "DISPATCH_CANDIDATE_UNRESOLVED",
                        "message": (
                            f"dispatch candidate {candidate!r} for "
                            f"{expression or '<unknown>'} could not be resolved"
                        ),
                    }
                )
        return sorted(set(resolved))

    def resolve(self, site: CallSite) -> DispatchResolution:
        """Resolve candidate functions for one dynamic dispatch site."""

        fn = self.analysis.function_by_id.get(site.from_function_id)
        module = next(
            (item for item in self.analysis.modules if item.name == fn.module_name),
            None,
        ) if fn is not None else None
        if module is None:
            module = next(
                (item for item in self.analysis.modules if item.module_id == site.from_module_id),
                None,
            )
        expression = site.callee_text or site.call_text or ""
        occurrence = self._occurrence_by_call_site.get(site.id, 1)
        matching_hints = [
            hint for hint in self.hints
            if resolve_function_ref(self.analysis, module, hint.function) == site.from_function_id
            and (not hint.expression or hint.expression == site.callee_text)
        ]
        hint = (
            matching_hints[min(occurrence - 1, len(matching_hints) - 1)]
            if matching_hints
            else None
        )
        comment = parse_dispatch_comment(
            description_comment(module.lines if module else [], site.line)
        )
        declared_complete = bool(hint and hint.complete) or bool(comment and comment.get("complete"))
        candidates: list[str] = []
        candidate_source = "unknown"
        reason = "dynamic_dispatch"
        if site.polymorphic:
            candidates.extend(site.candidates)
            candidate_source = "polymorphic"
            reason = "polymorphic_dispatch"
        if hint and hint.candidates:
            candidates.extend(
                self._resolve_candidates(
                    self.analysis, module, hint.candidates, expression=expression
                )
            )
            candidate_source = "config"
            reason = hint.reason or reason
        if comment and comment.get("candidates"):
            candidates.extend(
                self._resolve_candidates(
                    self.analysis, module, comment["candidates"], expression=expression
                )
            )
            candidate_source = "comment" if candidate_source == "unknown" else candidate_source
            reason = comment.get("reason") or reason
        if not declared_complete and not site.polymorphic:
            static_candidates: list[str] = []
            if site.callee_text.endswith(".func"):
                static_candidates.extend(self.argparse_candidates)
                if static_candidates:
                    candidate_source = "argparse_registry" if candidate_source == "unknown" else candidate_source
            registry = self.registry_candidates.get(fn.module_name if fn else "", {})
            for name, values in registry.items():
                if site.callee_text.startswith(f"{name}["):
                    static_candidates.extend(values)
                    candidate_source = "static_registry" if candidate_source == "unknown" else candidate_source
            candidates.extend(static_candidates)
        candidates = sorted(set(candidates))
        return DispatchResolution(
            candidates=candidates,
            candidate_set_complete=declared_complete,
            candidate_source=candidate_source,
            reason=reason,
            unresolved_reason=None if candidates else "dynamic_callable_not_inferable",
        )
