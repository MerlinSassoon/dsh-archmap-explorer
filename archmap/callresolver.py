from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from .analysis import AnalysisResult, FunctionInfo, ModuleInfo


@dataclass
class ResolvedCall:
    name: str
    qualified_name: str = ""
    target_function_id: str | None = None
    resolved: bool = False
    external: bool = False
    recursive: bool = False
    confidence: str = "low"
    candidates: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualifiedName": self.qualified_name,
            "targetFunctionId": self.target_function_id,
            "resolved": self.resolved,
            "external": self.external,
            "recursive": self.recursive,
            "confidence": self.confidence,
            "candidates": list(self.candidates),
        }


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


class CallResolver:
    def __init__(self, analysis: AnalysisResult) -> None:
        self.analysis = analysis
        self.module_by_name = {module.name: module for module in analysis.modules}
        self.module_by_id = {module.module_id: module for module in analysis.modules}

    def _find_module_function(self, module: ModuleInfo, name: str) -> FunctionInfo | None:
        return module.functions.get(name)

    def _is_package(self, module: ModuleInfo) -> bool:
        return module.file.rel_path.endswith("__init__.py")

    def _resolve_module_name(self, current: ModuleInfo, ref: Any) -> str | None:
        if ref.level <= 0:
            return ref.module or None
        parts = current.name.split(".")
        base = parts if self._is_package(current) else parts[:-1]
        up = ref.level - 1
        if up > len(base):
            return None
        if up:
            base = base[:-up]
        if ref.module:
            base = base + ref.module.split(".")
        return ".".join(base) if base else None

    def _imported_target_module(self, current: ModuleInfo, ref: Any) -> ModuleInfo | None:
        module_name = self._resolve_module_name(current, ref)
        if not module_name:
            return None
        return self.module_by_name.get(module_name)

    def _find_class_method(self, module: ModuleInfo, class_name: str, name: str) -> FunctionInfo | None:
        cls = module.classes.get(class_name)
        if cls is None:
            for candidate in module.classes.values():
                if candidate.name == class_name:
                    cls = candidate
                    break
        if cls is None:
            ref = module.imports.get(class_name)
            if ref is not None:
                target_module = self._imported_target_module(module, ref)
                if target_module is not None:
                    cls = target_module.classes.get(ref.name or class_name)
        if cls is None:
            return None
        return cls.methods.get(name)

    def _resolve_imported(
        self,
        current: ModuleInfo,
        ref: Any,
        attr_name: str,
        visited: set[tuple[str, str]] | None = None,
    ) -> FunctionInfo | None:
        target_module = self._imported_target_module(current, ref)
        if target_module is None:
            return None
        if ref.name:
            direct = target_module.functions.get(ref.name)
            if direct is not None:
                return direct
            # Follow re-exports declared in package __init__ modules.
            nested = target_module.imports.get(ref.name)
            if nested is None:
                return None
            seen = visited if visited is not None else set()
            key = (target_module.name, ref.name)
            if key in seen:
                return None
            seen.add(key)
            return self._resolve_imported(target_module, nested, ref.name, seen)
        return target_module.functions.get(attr_name)

    def _candidates(self, nodes: list[FunctionInfo]) -> list[str]:
        return sorted({node.id for node in nodes})

    def resolve(self, call: ast.Call, current_fn: FunctionInfo) -> ResolvedCall:
        current_module = self.module_by_name.get(current_fn.module_name)
        if current_module is None:
            return ResolvedCall(name="?", external=True, confidence="low")
        func = call.func
        candidates: list[FunctionInfo] = []

        if isinstance(func, ast.Name):
            name = func.id
            if name in current_module.functions:
                candidates.append(current_module.functions[name])
            if name in current_module.classes:
                init = current_module.classes[name].methods.get("__init__")
                if init:
                    candidates.append(init)
            ref = current_module.imports.get(name)
            if ref is not None:
                imported = self._resolve_imported(current_module, ref, name)
                if imported:
                    candidates.append(imported)
                elif ref.name:
                    target_module = self._imported_target_module(current_module, ref)
                    cls = target_module.classes.get(ref.name) if target_module else None
                    if cls and cls.methods.get("__init__"):
                        candidates.append(cls.methods["__init__"])
            if not candidates:
                if name in dir(__builtins__) or name in {"print", "len", "open", "input", "range", "super", "isinstance"}:
                    return ResolvedCall(name=name, external=True, confidence="high")
                # Method name available through self? Fall through to unresolved.
                return ResolvedCall(name=name, confidence="low")
            return self._finish(name, candidates, current_fn)

        if isinstance(func, ast.Attribute):
            name = func.attr
            if isinstance(func.value, ast.Name):
                base = func.value.id
                ref = current_module.imports.get(base)
                if ref is not None:
                    imported = self._resolve_imported(current_module, ref, name)
                    if imported:
                        candidates.append(imported)
                if base == "self" and current_fn.class_name:
                    method = self._find_class_method(current_module, current_fn.class_name, name)
                    if method:
                        candidates.append(method)
                module = self.module_by_name.get(base)
                if module is not None:
                    fn = module.functions.get(name)
                    if fn:
                        candidates.append(fn)
                # Type-annotated parameter / local variable.
                if not candidates and base in {"cls", "super"} and current_fn.class_name:
                    method = self._find_class_method(current_module, current_fn.class_name, name)
                    if method:
                        candidates.append(method)
                if not candidates:
                    type_name = self._find_local_type(current_fn.node, base)
                    if type_name:
                        method = self._find_class_method(current_module, type_name, name)
                        if method:
                            candidates.append(method)
                if not candidates:
                    # Class.method() form inside this module.
                    method = self._find_class_method(current_module, base, name)
                    if method:
                        candidates.append(method)
            full = ast.unparse(func)
            if candidates:
                return self._finish(full, candidates, current_fn)
            if isinstance(func.value, ast.Name) and func.value.id in current_module.imports:
                ref = current_module.imports[func.value.id]
                resolved_module = self._resolve_module_name(current_module, ref) or ref.module
                return ResolvedCall(
                    name=full,
                    qualified_name=f"{resolved_module}.{name}",
                    external=True,
                    confidence="medium",
                )
            return ResolvedCall(name=full, qualified_name=full, confidence="low")

        return ResolvedCall(name=ast.unparse(func), confidence="low")

    def _find_local_type(self, fn_node: ast.AST, name: str) -> str | None:
        if not isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        for arg in list(fn_node.args.posonlyargs) + list(fn_node.args.args) + list(fn_node.args.kwonlyargs):
            if arg.arg == name:
                return _annotation_name(arg.annotation)

        def search(stmts: list[ast.stmt]) -> str | None:
            for stmt in stmts:
                if isinstance(stmt, ast.With):
                    for item in stmt.items:
                        if isinstance(item.optional_vars, ast.Name) and item.optional_vars.id == name:
                            expr = item.context_expr
                            if isinstance(expr, ast.Call):
                                if isinstance(expr.func, ast.Name):
                                    return expr.func.id
                                if isinstance(expr.func, ast.Attribute):
                                    return expr.func.attr
                            if isinstance(expr, ast.Name):
                                return expr.id
                    found = search(stmt.body)
                    if found:
                        return found
                elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
                    return _annotation_name(stmt.annotation)
                elif isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == name and isinstance(stmt.value, ast.Call):
                            ctor = stmt.value.func
                            if isinstance(ctor, ast.Name):
                                return ctor.id
                            if isinstance(ctor, ast.Attribute):
                                return ctor.attr
                elif isinstance(stmt, ast.If):
                    found = search(stmt.body) or search(stmt.orelse)
                    if found:
                        return found
                elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While, ast.Try)):
                    found = search(stmt.body)
                    if found:
                        return found
                    if isinstance(stmt, ast.Try):
                        for handler in stmt.handlers:
                            found = search(handler.body)
                            if found:
                                return found
            return None

        return search(fn_node.body)

    def _finish(self, name: str, candidates: list[FunctionInfo], current_fn: FunctionInfo) -> ResolvedCall:
        unique: dict[str, FunctionInfo] = {item.id: item for item in candidates}
        values = [unique[key] for key in sorted(unique)]
        target = values[0]
        return ResolvedCall(
            name=name,
            qualified_name=f"{target.module_name}.{target.qualname}",
            target_function_id=target.id,
            resolved=True,
            external=False,
            recursive=target.id == current_fn.id,
            confidence="high" if len(values) == 1 else "medium",
            candidates=self._candidates(values),
        )
