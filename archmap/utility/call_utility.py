"""AST call-collection helpers shared by the Python frontend."""

from __future__ import annotations

import ast
import builtins

from ..model.analysis_model import FunctionInfo


BUILTIN_NAMES = set(dir(builtins))


def _annotation_name(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _annotation_name(node.value)
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.split(".")[-1]
    return None
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
