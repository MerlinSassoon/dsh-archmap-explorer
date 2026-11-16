from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Iterable

from .analysis import AnalysisResult, FunctionInfo
from .callresolver import CallResolver


@dataclass
class CallSite:
    """A single static call site discovered inside a function or method."""

    id: str
    from_function_id: str
    from_module_id: str
    to_function_id: str | None
    to_module_id: str | None
    file: str
    line: int
    column: int
    callee_text: str
    call_text: str
    kind: str
    resolved: bool
    external: bool
    recursive: bool
    confidence: str
    candidates: list[str] = field(default_factory=list)
    argument_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fromFunctionId": self.from_function_id,
            "fromModuleId": self.from_module_id,
            "toFunctionId": self.to_function_id,
            "toModuleId": self.to_module_id,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "calleeText": self.callee_text,
            "callText": self.call_text,
            "kind": self.kind,
            "resolved": self.resolved,
            "external": self.external,
            "recursive": self.recursive,
            "confidence": self.confidence,
            "candidates": list(self.candidates),
            "argumentCount": self.argument_count,
        }


class _CallVisitor(ast.NodeVisitor):
    """Collect calls in one function body without descending into nested defs."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)


def _unparse(node: ast.AST | None, limit: int = 300) -> str:
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except Exception:
        text = ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _calls_in_function(fn: FunctionInfo) -> list[ast.Call]:
    visitor = _CallVisitor()
    body = getattr(fn.node, "body", [])
    for stmt in body:
        visitor.visit(stmt)
    return visitor.calls


def collect_call_sites(
    analysis: AnalysisResult, functions: Iterable[FunctionInfo] | None = None
) -> list[CallSite]:
    fn_by_id = analysis.function_by_id
    resolver = CallResolver(analysis)
    result: list[CallSite] = []
    selected = list(functions) if functions is not None else analysis.functions
    for fn in sorted(selected, key=lambda item: (item.file, item.line, item.id)):
        for ordinal, call in enumerate(_calls_in_function(fn), start=1):
            resolved = resolver.resolve(call, fn)
            target = fn_by_id.get(resolved.target_function_id or "")
            line = int(getattr(call, "lineno", fn.line) or fn.line)
            column = int(getattr(call, "col_offset", 0) or 0) + 1
            callee_text = _unparse(call.func, 180)
            call_text = _unparse(call, 300)
            kind = "instantiate" if target is not None and target.name == "__init__" else "call"
            result.append(
                CallSite(
                    id=f"call:{fn.id}:{line}:{column}:{ordinal}",
                    from_function_id=fn.id,
                    from_module_id=fn.module_id,
                    to_function_id=resolved.target_function_id,
                    to_module_id=target.module_id if target is not None else None,
                    file=fn.file,
                    line=line,
                    column=column,
                    callee_text=callee_text,
                    call_text=call_text,
                    kind=kind,
                    resolved=resolved.resolved,
                    external=resolved.external,
                    recursive=resolved.recursive,
                    confidence=resolved.confidence,
                    candidates=list(resolved.candidates),
                    argument_count=len(call.args) + len(call.keywords),
                )
            )
    return result


def build_call_sites(analysis: AnalysisResult) -> list[dict[str, Any]]:
    return [site.as_dict() for site in collect_call_sites(analysis)]
