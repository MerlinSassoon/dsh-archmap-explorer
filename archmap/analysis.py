from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .config import ProjectConfig
from .discover import SourceFile


BUILTIN_NAMES = set(dir(builtins))


@dataclass
class ImportRef:
    alias: str
    module: str
    name: str | None = None
    level: int = 0


@dataclass
class FunctionInfo:
    id: str
    name: str
    qualname: str
    module_name: str
    module_id: str
    file: str
    line: int
    end_line: int
    signature: str
    is_async: bool
    note: str
    node: ast.AST
    class_name: str | None = None
    source_file: SourceFile | None = None
    synthetic: bool = False


@dataclass
class ClassInfo:
    name: str
    qualname: str
    module_name: str
    node: ast.ClassDef
    methods: dict[str, FunctionInfo] = field(default_factory=dict)
    bases: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    name: str
    module_id: str
    file: SourceFile
    tree: ast.Module
    source: str
    lines: list[str]
    imports: dict[str, ImportRef] = field(default_factory=dict)
    functions: dict[str, FunctionInfo] = field(default_factory=dict)
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    top_level: list[ast.stmt] = field(default_factory=list)


@dataclass
class AnalysisResult:
    config: ProjectConfig
    modules: list[ModuleInfo]
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    diagnostics: list[dict[str, Any]]
    source_by_file: dict[str, str]
    line_cache: dict[str, list[str]]
    function_by_id: dict[str, FunctionInfo]
    function_by_qualname: dict[str, FunctionInfo]
    method_index: dict[tuple[str, str], FunctionInfo]


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {_unparse(arg.annotation)}"
        if default is not None:
            text += f" = {_unparse(default)}"
        parts.append(text)
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {_unparse(arg.annotation)}"
        if default is not None:
            text += f" = {_unparse(default)}"
        parts.append(text)
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    result = f"{prefix} {node.name}({', '.join(parts)})"
    if node.returns is not None:
        result += f" -> {_unparse(node.returns)}"
    return result


def _first_paragraph(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    para = re.split(r"\n\s*\n", text, maxsplit=1)[0]
    return re.sub(r"\s+", " ", para).strip()


def _comment_note(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    doc = ast.get_docstring(node, clean=False)
    if doc:
        return _first_paragraph(doc)
    first_body_line = node.body[0].lineno if node.body else node.lineno
    idx = first_body_line - 2
    collected: list[str] = []
    while idx >= node.lineno:
        stripped = lines[idx].strip()
        if stripped.startswith("#"):
            collected.append(stripped.lstrip("#").strip())
            idx -= 1
            continue
        break
    if collected:
        return _first_paragraph(" ".join(reversed(collected)))
    idx = node.lineno - 2
    collected = []
    while idx >= 0:
        stripped = lines[idx].strip()
        if stripped.startswith("#"):
            collected.append(stripped.lstrip("#").strip())
            idx -= 1
            continue
        break
    return _first_paragraph(" ".join(reversed(collected)))


def _parse_imports(tree: ast.Module) -> dict[str, ImportRef]:
    imports: dict[str, ImportRef] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = ImportRef(
                    alias=alias.asname or alias.name.split(".")[0],
                    module=alias.name,
                )
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                imports[alias.asname or alias.name] = ImportRef(
                    alias=alias.asname or alias.name,
                    module=base,
                    name=alias.name,
                    level=node.level,
                )
    return imports


def _is_main_guard(stmt: ast.If) -> bool:
    test = stmt.test
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    left, comparator = test.left, test.comparators[0]
    if not isinstance(left, ast.Name) or left.id != "__name__":
        return False
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"


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
                    )
                    module.functions[qualname] = info
                    functions.append(info)
                    # Nested functions are indexed but not descended into for class methods.
                elif isinstance(child, ast.ClassDef):
                    qualname = f"{qual_prefix}{child.name}"
                    cls = ClassInfo(
                        name=child.name,
                        qualname=qualname,
                        module_name=module.name,
                        node=child,
                        bases=[_unparse(base) for base in child.bases],
                    )
                    for member in child.body:
                        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            mqual = f"{qualname}.{member.name}"
                            fn_id = f"fn:{module.name}.{mqual}"
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
                            )
                            cls.methods[member.name] = info
                            module.functions[mqual] = info
                            functions.append(info)
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

    return AnalysisResult(
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
