"""Python-frontend analysis stage implementation."""

from __future__ import annotations

import ast
from typing import Any, Iterable

from ...config.project_config import ProjectConfig
from ...model.analysis_model import (
    AnalysisResult,
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    SourceFile,
)
from .type_utility import resolve_type_hierarchy
from ...utility.analysis_utility import (
    _api_exposure,
    _class_kind,
    _comment_note,
    _decorator_names,
    _has_abstract_decorator,
    _is_abstract_class,
    _is_main_guard,
    _method_kind,
    _note_for_def,
    _parse_imports,
    _signature,
    _unparse,
    _visibility,
)


def analyze_project(config: ProjectConfig, sources: Iterable[SourceFile]) -> AnalysisResult:
    diagnostics: list[dict[str, Any]] = []
    modules: list[ModuleInfo] = []
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    source_by_file: dict[str, str] = {}
    line_cache: dict[str, list[str]] = {}

    for source_file in sorted(sources, key=lambda item: item.rel_path):
        try:
            source = source_file.path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=source_file.rel_path)
        except (OSError, SyntaxError, UnicodeError) as exc:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "SYNTAX_ERROR",
                    "message": f"{source_file.rel_path}: {exc}",
                    "file": source_file.rel_path,
                }
            )
            continue
        lines = source.splitlines()
        source_by_file[source_file.rel_path] = source
        line_cache[source_file.rel_path] = lines
        module = ModuleInfo(
            name=source_file.module_name,
            module_id=source_file.module_id,
            file=source_file,
            tree=tree,
            source=source,
            lines=lines,
            imports=_parse_imports(tree),
            top_level=list(tree.body),
        )

        def visit(node: ast.AST, qual_prefix: str = "", class_name: str | None = None) -> None:
            for child in getattr(node, "body", []):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = f"{qual_prefix}{child.name}"
                    fn_id = f"fn:{module.name}.{qualname}"
                    exposure, exposure_source, exposure_confidence = _api_exposure(
                        child, lines, module.name, qualname, config
                    )
                    info = FunctionInfo(
                        id=fn_id,
                        name=child.name,
                        qualname=qualname,
                        module_name=module.name,
                        module_id=module.module_id,
                        file=source_file.rel_path,
                        line=child.lineno,
                        end_line=getattr(child, "end_lineno", child.lineno) or child.lineno,
                        signature=_signature(child),
                        is_async=isinstance(child, ast.AsyncFunctionDef),
                        note=_comment_note(lines, child),
                        node=child,
                        class_name=class_name,
                        source_file=source_file,
                        method_kind="function",
                        visibility=_visibility(child.name),
                        is_abstract=_has_abstract_decorator(child),
                        api_exposure=exposure,
                        api_exposure_source=exposure_source,
                        api_exposure_confidence=exposure_confidence,
                    )
                    module.functions[qualname] = info
                    functions.append(info)
                    # Nested functions are indexed but not descended into for class methods.
                elif isinstance(child, ast.ClassDef):
                    qualname = f"{qual_prefix}{child.name}"
                    class_bases = [
                        _unparse(base).split("[", 1)[0].strip()
                        for base in child.bases
                    ]
                    cls = ClassInfo(
                        name=child.name,
                        qualname=qualname,
                        module_name=module.name,
                        node=child,
                        bases=class_bases,
                        module_id=module.module_id,
                        file=source_file.rel_path,
                        line=child.lineno,
                        end_line=getattr(child, "end_lineno", child.lineno) or child.lineno,
                        note=_note_for_def(child, lines),
                        decorators=_decorator_names(child),
                    )
                    for member in child.body:
                        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            mqual = f"{qualname}.{member.name}"
                            fn_id = f"fn:{module.name}.{mqual}"
                            member_decorators = _decorator_names(member)
                            exposure, exposure_source, exposure_confidence = _api_exposure(
                                member, lines, module.name, mqual, config
                            )
                            info = FunctionInfo(
                                id=fn_id,
                                name=member.name,
                                qualname=mqual,
                                module_name=module.name,
                                module_id=module.module_id,
                                file=source_file.rel_path,
                                line=member.lineno,
                                end_line=getattr(member, "end_lineno", member.lineno) or member.lineno,
                                signature=_signature(member),
                                is_async=isinstance(member, ast.AsyncFunctionDef),
                                note=_comment_note(lines, member),
                                node=member,
                                class_name=qualname,
                                source_file=source_file,
                                method_kind=_method_kind(member.name, member_decorators),
                                visibility=_visibility(member.name),
                                is_abstract=_has_abstract_decorator(member),
                                api_exposure=exposure,
                                api_exposure_source=exposure_source,
                                api_exposure_confidence=exposure_confidence,
                            )
                            cls.methods[member.name] = info
                            module.functions[mqual] = info
                            functions.append(info)
                    cls.is_abstract = _is_abstract_class(child, class_bases, list(cls.methods.values()))
                    cls.class_kind = _class_kind(child, class_bases, list(cls.methods.values()))
                    module.classes[qualname] = cls
                    classes.append(cls)

        visit(tree)
        modules.append(module)

    # A script module with an ``if __name__ == "__main__":`` guard receives a
    # synthetic function containing top-level executable statements and the guard body.
    for module in list(modules):
        guard_body: list[ast.stmt] | None = None
        for stmt in module.tree.body:
            if isinstance(stmt, ast.If) and _is_main_guard(stmt):
                guard_body = list(stmt.body)
                break
        if guard_body is None:
            continue
        selected: list[ast.stmt] = []
        for stmt in module.tree.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, ast.If) and _is_main_guard(stmt):
                selected.extend(stmt.body)
            else:
                selected.append(stmt)
        if not selected:
            continue
        fake = ast.FunctionDef(
            name="__main__",
            args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=selected,
            decorator_list=[],
        )
        first = selected[0]
        fake.lineno = getattr(first, "lineno", 1)
        fake.end_lineno = getattr(selected[-1], "end_lineno", getattr(selected[-1], "lineno", 1))
        fake.col_offset = 0
        ast.fix_missing_locations(fake)
        info = FunctionInfo(
            id=f"fn:{module.name}.__main__",
            name="__main__",
            qualname="__main__",
            module_name=module.name,
            module_id=module.module_id,
            file=module.file.rel_path,
            line=fake.lineno,
            end_line=fake.end_lineno or fake.lineno,
            signature="__main__()",
            is_async=False,
            note="程序入口：模块顶层代码与 __main__ guard。",
            node=fake,
            class_name=None,
            source_file=module.file,
            synthetic=True,
            method_kind="function",
            visibility="public",
            is_abstract=False,
            api_exposure="public",
            api_exposure_source="entrypoint",
            api_exposure_confidence="high",
        )
        module.functions["__main__"] = info
        functions.append(info)

    function_by_id = {fn.id: fn for fn in functions}
    function_by_qualname: dict[str, FunctionInfo] = {}
    method_index: dict[tuple[str, str], FunctionInfo] = {}
    for fn in functions:
        function_by_qualname.setdefault(f"{fn.module_name}.{fn.qualname}", fn)
        function_by_qualname.setdefault(fn.qualname, fn)
        if fn.class_name:
            method_index[(f"{fn.module_name}.{fn.class_name}", fn.name)] = fn
            method_index[(fn.class_name, fn.name)] = fn

    analysis = AnalysisResult(
        config=config,
        modules=modules,
        functions=functions,
        classes=classes,
        diagnostics=diagnostics,
        source_by_file=source_by_file,
        line_cache=line_cache,
        function_by_id=function_by_id,
        function_by_qualname=function_by_qualname,
        method_index=method_index,
    )
    resolve_type_hierarchy(analysis)
    return analysis
