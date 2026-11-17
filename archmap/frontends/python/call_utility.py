"""Python-frontend call extraction stage implementation."""

from __future__ import annotations

import ast
from typing import Any, Iterable

from ...model.analysis_model import AnalysisResult, FunctionInfo, ModuleInfo
from ...model.call_model import CallSite, ResolvedCall
from ...utility.call_utility import (
    BUILTIN_NAMES,
    _annotation_name,
    _calls_in_function,
    _unparse,
)


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
                if name in BUILTIN_NAMES:
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
