"""AST analysis helpers shared by the Python frontend."""

from __future__ import annotations

import ast
import re

from ..config.project_config import (
    DEFAULT_INTERNAL_API_TAGS,
    DEFAULT_PUBLIC_API_TAGS,
    ProjectConfig,
)
from ..model.analysis_model import FunctionInfo, ImportRef


PUBLIC_DECORATOR_NAMES = {"public_api", "api_public", "publicapi", "public"}
INTERNAL_DECORATOR_NAMES = {"internal_api", "api_internal", "internalapi", "internal"}
API_TAGGED_RE = re.compile(r"^\s*API\s*[:：]\s*(public|internal)\b", re.IGNORECASE)
LIFECYCLE_METHOD_NAMES = {
    "__enter__", "__exit__", "__aenter__", "__aexit__", "__call__",
    "__iter__", "__next__", "__aiter__", "__anext__",
}
ABSTRACT_METHOD_DECORATORS = {
    "abstractmethod", "abstractclassmethod", "abstractstaticmethod", "abstractproperty",
}
ENTRY_METHOD_NAMES = {"run", "main", "handle", "execute", "start", "serve", "dispatch"}


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
        f"fn:{module_name}.{qualname}",
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
    if name.startswith("_") or name.startswith(("do_", "log_")):
        return "internal", "naming", "high"
    return "public", "naming", "medium"


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
