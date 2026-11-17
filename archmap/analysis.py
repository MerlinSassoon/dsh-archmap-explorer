from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .config import DEFAULT_INTERNAL_API_TAGS, DEFAULT_PUBLIC_API_TAGS, ProjectConfig
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
    method_kind: str = "function"
    visibility: str = "public"
    is_abstract: bool = False
    api_exposure: str = "public"
    api_exposure_source: str = "naming"
    api_exposure_confidence: str = "medium"


@dataclass
class ClassInfo:
    name: str
    qualname: str
    module_name: str
    node: ast.ClassDef
    methods: dict[str, FunctionInfo] = field(default_factory=dict)
    bases: list[str] = field(default_factory=list)
    module_id: str = ""
    file: str = ""
    line: int = 0
    end_line: int = 0
    note: str = ""
    decorators: list[str] = field(default_factory=list)
    is_abstract: bool = False
    class_kind: str = "service"


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


PUBLIC_DECORATOR_NAMES = {"public_api", "api_public", "publicapi", "public"}
INTERNAL_DECORATOR_NAMES = {"internal_api", "api_internal", "internalapi", "internal"}
API_TAGGED_RE = re.compile(r"^\s*API\s*[:：]\s*(public|internal)\b", re.IGNORECASE)


def _leading_comment_text(lines: list[str], node: ast.AST) -> str:
    lineno = int(getattr(node, "lineno", 1) or 1)
    idx = lineno - 2
    collected: list[str] = []
    while idx >= 0:
        stripped = lines[idx].strip()
        if stripped.startswith("#"):
            collected.append(stripped.lstrip("#").strip())
            idx -= 1
            continue
        break
    return " ".join(reversed(collected)).strip()


def _tag_matches(text: str, tags: list[str]) -> bool:
    if not text:
        return False
    stripped = text.lstrip()
    while stripped[:1] in {"[", "("}:
        stripped = stripped[1:].lstrip()
    for tag in tags:
        candidate = str(tag or "").strip()
        if not candidate:
            continue
        if stripped.lower().startswith(candidate.lower()):
            return True
    return False


def _api_exposure(
    node: ast.AST,
    lines: list[str],
    module_name: str,
    qualname: str,
    config: ProjectConfig,
) -> tuple[str, str, str]:
    """Return ``(exposure, source, confidence)`` for a function or method.

    Explicit config wins.  Then decorators, then docstring/comment tags.  The
    fallback is language naming convention: underscore-prefixed names are
    internal, everything else is an inferred public surface.  Magic methods are
    kept as internal at the method level; protocol capabilities are synthesized
    by the frontend capability builder instead of exposing dunders directly.
    """
    override_keys = [
        f"{module_name}.{qualname}",
        qualname,
        f"{module_name}.{node.name}",
        node.name,
    ]
    for key in override_keys:
        value = config.api_exposure_overrides.get(key)
        if value in {"public", "internal"}:
            return value, "config", "high"

    decorator_names = _decorator_names(node)
    for name in decorator_names:
        tail = name.split(".")[-1].strip().lower()
        if tail in PUBLIC_DECORATOR_NAMES:
            return "public", "decorator", "high"
        if tail in INTERNAL_DECORATOR_NAMES:
            return "internal", "decorator", "high"

    doc = ""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        doc = ast.get_docstring(node, clean=False) or ""
    first_paragraph = _first_paragraph(doc)
    tagged = API_TAGGED_RE.match(first_paragraph)
    if tagged:
        return tagged.group(1).lower(), "docstring", "high"
    public_tags = config.contract_public_tags or DEFAULT_PUBLIC_API_TAGS
    internal_tags = config.contract_internal_tags or DEFAULT_INTERNAL_API_TAGS
    if _tag_matches(first_paragraph, public_tags):
        return "public", "docstring", "high"
    if _tag_matches(first_paragraph, internal_tags):
        return "internal", "docstring", "high"

    comment_text = _leading_comment_text(lines, node)
    if _tag_matches(comment_text, public_tags):
        return "public", "comment", "high"
    if _tag_matches(comment_text, internal_tags):
        return "internal", "comment", "high"

    name = getattr(node, "name", "")
    if name.startswith("_"):
        return "internal", "naming", "high"
    return "public", "naming", "medium"


LIFECYCLE_METHOD_NAMES = {
    "__enter__", "__exit__", "__aenter__", "__aexit__", "__call__",
    "__iter__", "__next__", "__aiter__", "__anext__",
}
ABSTRACT_METHOD_DECORATORS = {
    "abstractmethod", "abstractclassmethod", "abstractstaticmethod", "abstractproperty",
}
ENTRY_METHOD_NAMES = {"run", "main", "handle", "execute", "start", "serve", "dispatch"}


def _decorator_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for decorator in getattr(node, "decorator_list", []) or []:
        names.append(_unparse(decorator))
    return names


def _has_abstract_decorator(node: ast.AST) -> bool:
    return any(name.split(".")[-1] in ABSTRACT_METHOD_DECORATORS for name in _decorator_names(node))


def _visibility(name: str) -> str:
    if name == "__init__":
        return "constructor"
    if name in LIFECYCLE_METHOD_NAMES:
        return "lifecycle"
    if name.startswith("__") and name.endswith("__"):
        return "dunder"
    if name.startswith("_"):
        return "internal"
    return "public"


def _method_kind(name: str, decorators: list[str]) -> str:
    if name == "__init__":
        return "constructor"
    if name in LIFECYCLE_METHOD_NAMES:
        return "lifecycle"
    if any(item.split(".")[-1] in ABSTRACT_METHOD_DECORATORS for item in decorators):
        return "abstract"
    if name.startswith("__") and name.endswith("__"):
        return "dunder"
    if name.startswith("_"):
        return "internal"
    return "public_api"


def _note_for_def(node: ast.AST, lines: list[str]) -> str:
    doc = ast.get_docstring(node, clean=False) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else None
    if doc:
        return _first_paragraph(doc)
    return ""


def _is_abstract_class(node: ast.ClassDef, bases: list[str], methods: list[FunctionInfo]) -> bool:
    base_tails = {base.split(".")[-1] for base in bases}
    if base_tails.intersection({"ABC", "ABCMeta", "Protocol"}):
        return True
    return any(method.is_abstract for method in methods)


def _class_kind(node: ast.ClassDef, bases: list[str], methods: list[FunctionInfo]) -> str:
    base_tails = {base.split(".")[-1] for base in bases}
    decorators = {name.split(".")[-1] for name in _decorator_names(node)}
    if "Protocol" in base_tails:
        return "interface"
    if _is_abstract_class(node, bases, methods):
        return "abstract"
    if "dataclass" in decorators:
        return "dataclass"
    if base_tails.intersection({"Enum", "IntEnum", "Flag", "IntFlag", "StrEnum"}):
        return "enum"
    if any(base.endswith("Exception") or base.endswith("BaseException") or base.endswith("Error") for base in bases):
        return "exception"
    real_methods = [method for method in methods if method.name not in {"__init__", "__repr__", "__str__"}]
    if not real_methods:
        return "model"
    return "service"


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
                    class_bases = [_unparse(base) for base in child.bases]
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
