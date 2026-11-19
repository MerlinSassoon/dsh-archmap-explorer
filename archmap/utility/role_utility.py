"""Provider-role inference helpers."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from ..config.contract_config import PROVIDER_ROLES
from ..model.analysis_model import AnalysisResult, ClassInfo, FunctionInfo, ModuleInfo
from ..model.call_model import CallSite


ROLE_TAG_RE = re.compile(
    r"(?:provider\s*role|providerrole|role|提供者角色|角色)\s*[:：]\s*"
    r"(config|model|manager|adapter|component|contract|utility)\b",
    re.IGNORECASE,
)
CONFIG_NAME_SUFFIXES = {
    "config", "configuration", "settings", "options", "params", "parameters",
    "defaults", "constants", "env", "environment",
}
MODEL_NAME_SUFFIXES = {
    "model", "dto", "record", "result", "info", "payload", "entity", "view",
}
MANAGER_NAME_SUFFIXES = {
    "manager", "service", "controller", "coordinator", "orchestrator",
    "resolver", "builder", "engine", "frontend", "runner", "processor",
}
ADAPTER_NAME_SUFFIXES = {
    "adapter", "client", "gateway", "repository", "repo", "driver",
    "transport", "connection", "connector", "database", "store",
}
COMPONENT_NAME_SUFFIXES = {
    "component", "widget", "spinner", "dialog", "view", "screen", "panel",
    "handler", "server", "cli", "command", "console",
}
UTILITY_NAME_SUFFIXES = {
    "util", "utils", "utility", "helper", "helpers", "common", "tool", "tools",
}
EXTERNAL_ADAPTER_MODULES = {
    "aiohttp", "boto3", "grpc", "http", "httpx", "kafka", "mysql",
    "paramiko", "pika", "psycopg", "psycopg2", "pymysql", "redis",
    "requests", "serial", "socket", "sqlalchemy", "sqlite3", "ssl",
    "websockets",
}
EXTERNAL_IO_CALL_NAMES = {
    "connect", "send", "sendall", "recv", "recvfrom", "request", "urlopen",
    "execute", "executemany", "cursor", "commit", "rollback", "query",
    "get", "post", "put", "delete", "publish", "consume",
}


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _decorator_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for item in getattr(node, "decorator_list", []) or []:
        if isinstance(item, ast.Call):
            item = item.func
        names.append(_unparse(item))
    return names


def _first_paragraph(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    return re.split(r"\n\s*\n", text, maxsplit=1)[0].strip()


def _leading_comments(lines: list[str], node: ast.AST) -> str:
    idx = int(getattr(node, "lineno", 1) or 1) - 2
    collected: list[str] = []
    while idx >= 0:
        stripped = lines[idx].strip()
        if stripped.startswith("#"):
            collected.append(stripped.lstrip("#").strip())
            idx -= 1
            continue
        break
    return " ".join(reversed(collected)).strip()


def _metadata_role(
    node: ast.AST, lines: list[str]
) -> tuple[str, str, str] | None:
    """Read an explicit role annotation from decorators, docstring or comments."""
    for decorator in getattr(node, "decorator_list", []) or []:
        role: str | None = None
        if isinstance(decorator, ast.Call):
            tail = ""
            if isinstance(decorator.func, ast.Name):
                tail = decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                tail = decorator.func.attr
            if tail.lower().lstrip("_") in {"provider_role", "providerrole", "role"}:
                for arg in decorator.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        role = arg.value.strip().lower()
                        break
        elif isinstance(decorator, (ast.Name, ast.Attribute)):
            tail = decorator.id if isinstance(decorator, ast.Name) else decorator.attr
            if tail.lower() in PROVIDER_ROLES:
                role = tail.lower()
        if role in PROVIDER_ROLES:
            return role, "decorator", "high"

    doc = ""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        doc = ast.get_docstring(node, clean=False) or ""
    match = ROLE_TAG_RE.search(_first_paragraph(doc))
    if match:
        return match.group(1).lower(), "docstring", "high"
    match = ROLE_TAG_RE.search(_leading_comments(lines, node))
    if match:
        return match.group(1).lower(), "comment", "high"
    return None


def _provider_keys(
    provider_id: str, module_name: str, qualname: str, name: str
) -> list[str]:
    return [provider_id, f"{module_name}.{qualname}", qualname, name]


def _configured_role(
    config: Any,
    provider_id: str,
    module_name: str,
    qualname: str,
    name: str,
) -> str | None:
    for key in _provider_keys(provider_id, module_name, qualname, name):
        value = config.provider_role_overrides.get(key)
        if value in PROVIDER_ROLES:
            return value
    return None


def _configured_entry_ids(analysis: AnalysisResult) -> set[str]:
    found: set[str] = set()
    for spec in analysis.config.entrypoints:
        spec = spec.strip()
        if not spec:
            continue
        if ":" in spec:
            left, right = spec.rsplit(":", 1)
            module_tail = Path(left.removesuffix(".py")).name
            for fn in analysis.functions:
                if fn.name != right and fn.qualname != right:
                    continue
                if fn.module_name.split(".")[-1] == module_tail or fn.module_name == left:
                    found.add(fn.id)
        else:
            for fn in analysis.functions:
                if spec in {fn.name, fn.qualname, f"{fn.module_name}.{fn.qualname}"}:
                    found.add(fn.id)
    return found


def _has_annotation_assignments(node: ast.ClassDef) -> bool:
    return any(isinstance(stmt, ast.AnnAssign) for stmt in node.body)


def _has_class_assignments(node: ast.ClassDef) -> bool:
    return any(isinstance(stmt, (ast.Assign, ast.AnnAssign)) for stmt in node.body)


def _instance_attributes(cls: ClassInfo) -> set[str]:
    init = cls.methods.get("__init__")
    if init is None or not isinstance(init.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    names: set[str] = set()
    for node in ast.walk(init.node):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in {"self", "cls"}
            ):
                names.add(target.attr)
    return names


def _public_instance_methods(cls: ClassInfo) -> list[FunctionInfo]:
    result: list[FunctionInfo] = []
    for method in cls.methods.values():
        if method.name.startswith("_"):
            continue
        decorators = {part.split(".")[-1] for part in _decorator_names(method.node)}
        if decorators.intersection({"staticmethod", "classmethod"}):
            continue
        result.append(method)
    return result


def _static_like_public_methods(cls: ClassInfo) -> bool:
    public = [method for method in cls.methods.values() if not method.name.startswith("_")]
    if not public:
        return False
    for method in public:
        decorators = {part.split(".")[-1] for part in _decorator_names(method.node)}
        if not decorators.intersection({"staticmethod", "classmethod"}):
            return False
    return True


def _has_protocol_methods(cls: ClassInfo) -> bool:
    methods = set(cls.methods)
    return bool(
        {"__enter__", "__exit__"}.issubset(methods)
        or {"__aenter__", "__aexit__"}.issubset(methods)
        or "__call__" in methods
        or "__iter__" in methods
    )


def _external_aliases(module: ModuleInfo | None) -> set[str]:
    if module is None:
        return set()
    aliases: set[str] = set()
    for alias, ref in module.imports.items():
        root = (ref.module or ref.name or "").split(".")[0]
        if root in EXTERNAL_ADAPTER_MODULES:
            aliases.add(alias)
            aliases.add(root)
    return aliases


def _uses_external_io(node: ast.AST, module: ModuleInfo | None) -> bool:
    aliases = _external_aliases(module)
    if not aliases:
        # Builtin file/network primitives are still useful adapter evidence.
        aliases = {"open"}
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            if func.id in aliases or func.id in EXTERNAL_IO_CALL_NAMES:
                return True
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id in aliases:
                return True
            if func.attr in EXTERNAL_IO_CALL_NAMES and isinstance(func.value, ast.Name):
                if func.value.id in aliases:
                    return True
    return False


def _name_has_suffix(name: str, suffixes: set[str]) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    parts = normalized.split("_")
    return bool(set(parts).intersection(suffixes)) or normalized in suffixes


def _infer_class_role(
    cls: ClassInfo, module: ModuleInfo | None
) -> tuple[str, str, str]:
    base_tails = {base.split(".")[-1] for base in cls.bases}
    decorators = {name.split(".")[-1].lower() for name in _decorator_names(cls.node)}
    node = cls.node
    methods = cls.methods
    public_methods = _public_instance_methods(cls)
    instance_attrs = _instance_attributes(cls)

    if cls.is_abstract or cls.class_kind in {"abstract", "interface"} or base_tails.intersection({"ABC", "ABCMeta", "Protocol"}):
        return "contract", "structure", "high"
    if cls.class_kind == "enum" or base_tails.intersection({"Enum", "IntEnum", "Flag", "IntFlag", "StrEnum"}):
        return "config", "structure", "high"
    if _has_protocol_methods(cls):
        return "component", "structure", "high"

    is_dataclass = bool(decorators.intersection({"dataclass"}) or base_tails.intersection({"NamedTuple", "TypedDict"}))
    if is_dataclass:
        if _name_has_suffix(cls.name, CONFIG_NAME_SUFFIXES):
            return "config", "structure", "medium"
        return "model", "structure", "high"
    if cls.class_kind == "exception":
        return "model", "structure", "medium"

    if _uses_external_io(node, module):
        return "adapter", "structure", "medium"

    if _has_class_assignments(node) and not methods:
        return "config", "structure", "high"
    if _has_annotation_assignments(node) and not public_methods:
        return "model", "structure", "high"

    if _static_like_public_methods(cls) and not instance_attrs:
        return "utility", "structure", "medium"
    # Common structural/naming roles should win over the generic
    # "has public methods => manager" rule. Explicit decorator/docstring roles
    # and structural evidence still take precedence above this point.
    if _name_has_suffix(cls.name, ADAPTER_NAME_SUFFIXES):
        return "adapter", "naming", "low"
    if _name_has_suffix(cls.name, COMPONENT_NAME_SUFFIXES):
        return "component", "naming", "low"
    if public_methods:
        confidence = "high" if instance_attrs or len(public_methods) >= 2 else "medium"
        return "manager", "structure", confidence
    if _has_class_assignments(node):
        return "config", "structure", "medium"
    if _has_annotation_assignments(node):
        return "model", "structure", "medium"
    if _name_has_suffix(cls.name, COMPONENT_NAME_SUFFIXES):
        return "component", "naming", "low"
    if _name_has_suffix(cls.name, ADAPTER_NAME_SUFFIXES):
        return "adapter", "naming", "low"
    if _name_has_suffix(cls.name, CONFIG_NAME_SUFFIXES):
        return "config", "naming", "low"
    if _name_has_suffix(cls.name, MODEL_NAME_SUFFIXES):
        return "model", "naming", "low"
    if _name_has_suffix(cls.name, MANAGER_NAME_SUFFIXES):
        return "manager", "naming", "low"
    if _name_has_suffix(cls.name, UTILITY_NAME_SUFFIXES):
        return "utility", "naming", "low"
    return "utility", "structure", "medium"


def _has_control_flow(node: ast.AST) -> bool:
    return any(isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)) for child in ast.walk(node))


def _infer_function_role(
    fn: FunctionInfo,
    module: ModuleInfo | None,
    configured_entries: set[str],
    project_names: set[str],
) -> tuple[str, str, str]:
    """Infer a conservative base role for a module-level free function.

    P9 no longer promotes a public free function to ``manager`` merely because
    it contains control flow or calls project classes.  The effective free
    function surface is resolved separately; only explicit capability evidence
    upgrades a free function to a behavioral Provider role.
    """

    del configured_entries, project_names
    if fn.synthetic or fn.name == "__main__":
        return "utility", "structure", "high"
    if _uses_external_io(fn.node, module):
        return "adapter", "structure", "medium"
    return "utility", "structure", "medium"


def _provider_visibility(role: str, name: str, api_exposure: str) -> str:
    if role == "utility" or (name.startswith("_") and name != "__main__"):
        return "internal"
    if role in {"manager", "adapter", "component"} and api_exposure != "public":
        return "internal"
    return "public"


def _argument_defaults(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, tuple[str | None, str]]:
    args = node.args
    result: dict[str, tuple[str | None, str]] = {}
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        result[arg.arg] = (
            _unparse(arg.annotation) or None,
            _unparse(default) if default is not None else "",
        )
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        result[arg.arg] = (
            _unparse(arg.annotation) or None,
            _unparse(default) if default is not None else "",
        )
    return result


def _type_summary(cls: ClassInfo, role: str) -> dict[str, Any]:
    node = cls.node
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(name: str, annotation: str, default: str, kind: str) -> None:
        if not name or name in seen or name.startswith("__"):
            return
        seen.add(name)
        fields.append(
            {
                "name": name,
                "annotation": annotation,
                "default": default,
                "kind": kind,
            }
        )

    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            add(
                stmt.target.id,
                _unparse(stmt.annotation),
                _unparse(stmt.value) if stmt.value is not None else "",
                "field",
            )
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue
                member_kind = "enum_member" if cls.class_kind == "enum" else "constant"
                add(target.id, "", _unparse(stmt.value), member_kind)

    init = cls.methods.get("__init__")
    if init is not None and isinstance(init.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        defaults = _argument_defaults(init.node)
        for child in ast.walk(init.node):
            if not isinstance(child, (ast.Assign, ast.AnnAssign)):
                continue
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                if not (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in {"self", "cls"}
                ):
                    continue
                annotation = ""
                default = _unparse(child.value)
                if isinstance(child, ast.AnnAssign):
                    annotation = _unparse(child.annotation)
                if isinstance(child.value, ast.Name) and child.value.id in defaults:
                    arg_annotation, arg_default = defaults[child.value.id]
                    annotation = annotation or (arg_annotation or "")
                    default = arg_default or default
                add(target.attr, annotation, default, "instance_field")

    fields = fields[:24]
    return {
        "kind": "enum" if cls.class_kind == "enum" else role,
        "fieldCount": len(fields),
        "fields": fields,
    }


def _code_unit_role_for_file(file: str) -> str | None:
    """Return a strong role hint from the normalized file suffix.

    The hint is intentionally narrow: only ArchMap's own normalized projects
    use these suffixes.  Legacy projects without the convention fall back to
    metadata and structural heuristics.
    """
    if not file:
        return None
    path = Path(file)
    name = path.name.lower()
    if name.endswith("_utility.py"):
        return "utility"
    if name.endswith("_config.py"):
        return "config"
    if name.endswith("_model.py"):
        return "model"
    if name.endswith("_manager.py"):
        return "manager"
    if "entry" in path.parts:
        return None
    return None


def _infer_owner_ids(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite] | None,
) -> dict[str, str]:
    """Infer the single owning provider for free functions from resolved calls.

    A free function used by exactly one class manager (directly or transitively)
    belongs to that manager's internal implementation.  Shared utilities keep
    ``None`` as owner.
    """
    if not call_sites:
        return {}
    fn_by_id = {fn.id: fn for fn in analysis.functions}
    callers_by_callee: dict[str, list[str]] = defaultdict(list)
    for site in call_sites:
        if site.resolved and site.to_function_id:
            callers_by_callee[site.to_function_id].append(site.from_function_id)

    owners: dict[str, str] = {}
    for fn in analysis.functions:
        if fn.class_name:
            owners[fn.id] = f"cls:{fn.module_name}.{fn.class_name}"
    configured_entries = _configured_entry_ids(analysis)
    for fn in analysis.functions:
        if not fn.class_name and (fn.synthetic or fn.id in configured_entries):
            owners[fn.id] = fn.id

    free_functions = [fn for fn in analysis.functions if not fn.class_name]
    changed = True
    while changed:
        changed = False
        for fn in free_functions:
            if fn.id in owners:
                continue
            caller_owners = {
                owners[caller_id]
                for caller_id in callers_by_callee.get(fn.id, [])
                if caller_id in owners
            }
            if len(caller_owners) == 1:
                owners[fn.id] = next(iter(caller_owners))
                changed = True
    return owners
