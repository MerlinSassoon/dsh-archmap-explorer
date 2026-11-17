"""Python-frontend call extraction stage implementation."""

from __future__ import annotations

import ast
from typing import Any, Iterable

from ...model.analysis_model import AnalysisResult, ClassInfo, FunctionInfo, ModuleInfo
from ...model.call_model import CallSite, ResolvedCall
from ...utility.call_utility import (
    BUILTIN_NAMES,
    _annotation_name,
    _calls_in_function,
    _unparse,
)
from .type_utility import _resolve_class_expr, class_id


class CallResolver:
    def __init__(self, analysis: AnalysisResult) -> None:
        self.analysis = analysis
        self.module_by_name = {module.name: module for module in analysis.modules}
        self.module_by_id = {module.module_id: module for module in analysis.modules}
        self.class_by_id = {class_id(cls): cls for cls in analysis.classes}

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
        target = self.module_by_name.get(module_name)
        if target is not None:
            return target
        current_parts = current.name.split(".")
        package_parts = current_parts if self._is_package(current) else current_parts[:-1]
        for depth in range(len(package_parts), 0, -1):
            candidate = ".".join([*package_parts[:depth], *module_name.split(".")])
            target = self.module_by_name.get(candidate)
            if target is not None:
                return target
        suffix = "." + module_name
        matches = [module for name, module in self.module_by_name.items() if name.endswith(suffix)]
        return matches[0] if len(matches) == 1 else None

    def _class_for_name(self, current: ModuleInfo, name: str) -> ClassInfo | None:
        found, _ = _resolve_class_expr(self.analysis, current, name)
        return found

    def _find_class(self, module: ModuleInfo, class_name: str) -> ClassInfo | None:
        cls = self._class_for_name(module, class_name)
        if cls is not None:
            return cls
        tail = str(class_name).split(".")[-1]
        matches = [item for item in self.analysis.classes if item.name == tail]
        return matches[0] if len(matches) == 1 else None

    def _find_declared_method(self, cls: ClassInfo, name: str) -> FunctionInfo | None:
        """Find a method in the class's MRO (nearest definition wins)."""

        for cid in cls.mro_class_ids or [class_id(cls)]:
            current = self.class_by_id.get(cid)
            if current is None:
                continue
            method = current.methods.get(name)
            if method is not None:
                return method
        return None

    def _find_constructor(self, cls: ClassInfo) -> FunctionInfo | None:
        return self._find_declared_method(cls, "__init__")

    def _find_self_attribute_type(self, current_fn: FunctionInfo, attr_name: str) -> ClassInfo | None:
        """Resolve the declared/injected type of ``self.<attr>``."""

        if not current_fn.class_name:
            return None
        current_module = self.module_by_name.get(current_fn.module_name)
        if current_module is None:
            return None
        owner = self._find_class(current_module, current_fn.class_name)
        if owner is None:
            return None
        annotation = None
        for stmt in owner.node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == attr_name:
                annotation = stmt.annotation
                break
        init = owner.methods.get("__init__")
        if annotation is None and init is not None:
            for node in ast.walk(init.node):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr == attr_name
                    for target in targets
                ):
                    continue
                if isinstance(node, ast.AnnAssign):
                    annotation = node.annotation
                elif isinstance(node.value, ast.Name):
                    for arg in list(init.node.args.args) + list(init.node.args.kwonlyargs):
                        if arg.arg == node.value.id and arg.annotation is not None:
                            annotation = arg.annotation
                            break
                elif isinstance(node.value, ast.Call):
                    annotation = node.value.func
                break
        if annotation is None:
            return None
        return self._class_for_name(current_module, ast.unparse(annotation).split("[", 1)[0])

    def _descendant_implementations(self, cls: ClassInfo, name: str) -> list[FunctionInfo]:
        """Return concrete overrides below ``cls`` without sibling bleeding."""

        result: dict[str, FunctionInfo] = {}
        queue = list(cls.subclass_ids)
        seen: set[str] = set()
        while queue:
            cid = queue.pop(0)
            if cid in seen:
                continue
            seen.add(cid)
            child = self.class_by_id.get(cid)
            if child is None:
                continue
            method = child.methods.get(name)
            if method is not None and not method.is_abstract:
                result[method.id] = method
            queue.extend(child.subclass_ids)
        return [result[key] for key in sorted(result)]

    def _polymorphic_call(
        self,
        name: str,
        receiver: ClassInfo,
        method: FunctionInfo | None,
        candidates: list[FunctionInfo],
    ) -> ResolvedCall:
        qualified = method.qualname if method is not None else name
        return ResolvedCall(
            name=name,
            qualified_name=f"{receiver.module_name}.{qualified}",
            target_function_id=None,
            resolved=False,
            external=False,
            recursive=False,
            confidence="medium" if candidates else "low",
            candidates=[item.id for item in candidates],
            polymorphic=True,
            dispatch_kind="polymorphic",
        )

    def _resolve_method_on_class(
        self,
        name: str,
        cls: ClassInfo,
        *,
        allow_polymorphic: bool = True,
    ) -> ResolvedCall:
        method = self._find_declared_method(cls, name)
        contract_method = bool(
            method is not None
            and (
                method.is_abstract
                or (cls.class_kind == "interface" and method.class_name == cls.qualname)
            )
        )
        if contract_method and allow_polymorphic:
            candidates = self._descendant_implementations(cls, name)
            return self._polymorphic_call(name, cls, method, candidates)
        if method is None:
            if allow_polymorphic and cls.is_abstract:
                candidates = self._descendant_implementations(cls, name)
                if candidates:
                    return self._polymorphic_call(name, cls, method, candidates)
            return ResolvedCall(name=name, confidence="low")
        return ResolvedCall(
            name=name,
            qualified_name=f"{method.module_name}.{method.qualname}",
            target_function_id=method.id,
            resolved=True,
            external=False,
            recursive=False,
            confidence="high",
            candidates=[method.id],
            polymorphic=False,
            dispatch_kind="static",
        )

    def _find_imported_class_method(self, module: ModuleInfo, ref: Any, attr_name: str) -> FunctionInfo | None:
        target_module = self._imported_target_module(module, ref)
        if target_module is None:
            return None
        cls = None
        if ref.name:
            cls = next((item for item in target_module.classes.values() if item.name == ref.name), None)
        if cls is None:
            cls = next((item for item in target_module.classes.values() if item.name == attr_name), None)
        if cls is None:
            return None
        return self._find_declared_method(cls, attr_name)

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
                init = self._find_constructor(current_module.classes[name])
                if init:
                    candidates.append(init)
            ref = current_module.imports.get(name)
            if ref is not None:
                imported = self._resolve_imported(current_module, ref, name)
                if imported:
                    candidates.append(imported)
                elif ref.name:
                    target_module = self._imported_target_module(current_module, ref)
                    cls = None
                    if target_module is not None:
                        cls = next((item for item in target_module.classes.values() if item.name == ref.name), None)
                    if cls is not None:
                        init = self._find_constructor(cls)
                        if init is not None:
                            candidates.append(init)
            if not candidates:
                if name in BUILTIN_NAMES:
                    return ResolvedCall(name=name, external=True, confidence="high")
                return ResolvedCall(name=name, confidence="low")
            return self._finish(name, candidates, current_fn)

        if isinstance(func, ast.Attribute):
            name = func.attr
            receiver_expr = func.value

            # super().method(): statically target the nearest base declaration.
            if isinstance(receiver_expr, ast.Call) and isinstance(receiver_expr.func, ast.Name) and receiver_expr.func.id == "super":
                if current_fn.class_name:
                    current_cls = self._find_class(current_module, current_fn.class_name)
                    if current_cls is not None and len(current_cls.mro_class_ids) > 1:
                        base_cls = self.class_by_id.get(current_cls.mro_class_ids[1])
                        if base_cls is not None:
                            resolved = self._resolve_method_on_class(name, base_cls, allow_polymorphic=False)
                            if resolved.resolved:
                                return resolved
                return ResolvedCall(name=ast.unparse(func), confidence="low")

            # Constructed receiver: EchoWorker().run().
            if isinstance(receiver_expr, ast.Call):
                ctor = receiver_expr.func
                ctor_name = ""
                if isinstance(ctor, ast.Name):
                    ctor_name = ctor.id
                elif isinstance(ctor, ast.Attribute):
                    ctor_name = ast.unparse(ctor)
                receiver_cls = self._find_class(current_module, ctor_name) if ctor_name else None
                if receiver_cls is not None:
                    return self._resolve_method_on_class(name, receiver_cls)
                method = self._find_imported_class_method(current_module, current_module.imports.get(ctor_name), name) if ctor_name in current_module.imports else None
                if method is not None:
                    return ResolvedCall(
                        name=ast.unparse(func), qualified_name=f"{method.module_name}.{method.qualname}",
                        target_function_id=method.id, resolved=True, confidence="high",
                        candidates=[method.id],
                    )

            if isinstance(receiver_expr, ast.Name):
                base = receiver_expr.id
                # Module-level function via imported module alias.
                ref = current_module.imports.get(base)
                if ref is not None:
                    imported = self._resolve_imported(current_module, ref, name)
                    if imported:
                        candidates.append(imported)
                if base in {"self", "cls"} and current_fn.class_name:
                    current_cls = self._find_class(current_module, current_fn.class_name)
                    if current_cls is not None:
                        return self._resolve_method_on_class(name, current_cls)
                    fallback = next(
                        (
                            item
                            for item in self.analysis.classes
                            if item.qualname == current_fn.class_name
                            and item.module_name == current_fn.module_name
                        ),
                        None,
                    )
                    if fallback is not None:
                        return self._resolve_method_on_class(name, fallback)
                module = self.module_by_name.get(base)
                if module is not None:
                    fn = module.functions.get(name)
                    if fn:
                        candidates.append(fn)
                if not candidates:
                    type_name = self._find_local_type(current_fn.node, base)
                    if type_name:
                        receiver_cls = self._class_for_name(current_module, type_name)
                        if receiver_cls is not None:
                            return self._resolve_method_on_class(name, receiver_cls)
                if not candidates:
                    receiver_cls = self._find_class(current_module, base)
                    if receiver_cls is not None:
                        return self._resolve_method_on_class(name, receiver_cls)
            elif isinstance(receiver_expr, ast.Attribute):
                # self.attr.method(): resolve the attribute's declared/injected type.
                if (
                    isinstance(receiver_expr.value, ast.Name)
                    and receiver_expr.value.id == "self"
                ):
                    receiver_cls = self._find_self_attribute_type(current_fn, receiver_expr.attr)
                    if receiver_cls is not None:
                        return self._resolve_method_on_class(name, receiver_cls)
                # Module/class-qualified receiver such as pkg.Base.run().
                receiver_name = ast.unparse(receiver_expr)
                receiver_cls = self._find_class(current_module, receiver_name)
                if receiver_cls is not None:
                    return self._resolve_method_on_class(name, receiver_cls)

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
        if not values:
            return ResolvedCall(name=name, confidence="low")
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
            polymorphic=False,
            dispatch_kind="static",
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
            recursive = target.id == fn.id if target is not None else resolved.recursive
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
                    recursive=recursive,
                    confidence=resolved.confidence,
                    candidates=list(resolved.candidates),
                    argument_count=len(call.args) + len(call.keywords),
                    polymorphic=resolved.polymorphic,
                    dispatch_kind=resolved.dispatch_kind,
                )
            )
    return result


def build_call_sites(analysis: AnalysisResult) -> list[dict[str, Any]]:
    return [site.as_dict() for site in collect_call_sites(analysis)]
