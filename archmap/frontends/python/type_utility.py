"""Python type-hierarchy resolution and structural relation facts.

P3 keeps type discovery inside the language frontend.  The neutral graph layer
only consumes canonical class IDs and relation records; it never guesses a
Python base class from a display name.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from typing import Iterable

from ...model.analysis_model import AnalysisResult, ClassInfo, ImportRef, ModuleInfo


# Standard/library bases that are intentionally not modelled as ArchMap classes.
_EXTERNAL_BASE_HEADS = {
    "ABC",
    "ABCMeta",
    "Protocol",
    "Generic",
    "NamedTuple",
    "TypedDict",
    "Enum",
    "IntEnum",
    "Flag",
    "IntFlag",
    "StrEnum",
    "Exception",
    "BaseException",
    "Error",
    "object",
}


def class_id(cls: ClassInfo) -> str:
    return f"cls:{cls.module_name}.{cls.qualname}"


def _base_expression(node: ast.AST | None) -> str:
    """Return a base expression without generic arguments."""

    raw = ""
    try:
        raw = ast.unparse(node) if node is not None else ""
    except Exception:
        raw = ""
    raw = raw.strip()
    # ``Base[T]`` / ``typing.Protocol[T]``: the hierarchy target is the head.
    if "[" in raw:
        raw = raw.split("[", 1)[0].strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = raw[1:-1].strip()
    return raw


def _tail(value: str) -> str:
    return str(value or "").strip().split(".")[-1]


def _is_external_base(expr: str) -> bool:
    head = _tail(expr)
    return head in _EXTERNAL_BASE_HEADS or not head or head == "None"


def _is_package(module: ModuleInfo) -> bool:
    return module.file.rel_path.endswith("__init__.py")


def _resolve_module_name(current: ModuleInfo, ref: ImportRef) -> str | None:
    if ref.level <= 0:
        return ref.module or None
    parts = current.name.split(".")
    base = parts if _is_package(current) else parts[:-1]
    up = ref.level - 1
    if up > len(base):
        return None
    if up:
        base = base[:-up]
    if ref.module:
        base = base + ref.module.split(".")
    return ".".join(base) if base else None


def _imported_target_module(analysis: AnalysisResult, current: ModuleInfo, ref: ImportRef) -> ModuleInfo | None:
    module_name = _resolve_module_name(current, ref)
    if not module_name:
        return None
    by_name = {module.name: module for module in analysis.modules}
    direct = by_name.get(module_name)
    if direct is not None:
        return direct
    current_parts = current.name.split(".")
    package_parts = current_parts if _is_package(current) else current_parts[:-1]
    for depth in range(len(package_parts), 0, -1):
        candidate = ".".join([*package_parts[:depth], *module_name.split(".")])
        target = by_name.get(candidate)
        if target is not None:
            return target
    suffix = "." + module_name
    matches = [module for name, module in by_name.items() if name.endswith(suffix)]
    return matches[0] if len(matches) == 1 else None


def _class_in_module(module: ModuleInfo | None, expr: str) -> ClassInfo | None:
    if module is None:
        return None
    value = expr.strip()
    tail = _tail(value)
    direct = module.classes.get(value) or module.classes.get(tail)
    if direct is not None:
        return direct
    matches = [
        cls
        for cls in module.classes.values()
        if cls.name == tail or cls.qualname == value or cls.qualname.endswith("." + value)
    ]
    return matches[0] if len(matches) == 1 else None


def _find_exported_class(
    analysis: AnalysisResult,
    module: ModuleInfo | None,
    name: str,
    seen: set[tuple[str, str]] | None = None,
) -> ClassInfo | None:
    """Find a class locally or through a package's re-export chain."""

    if module is None:
        return None
    direct = _class_in_module(module, name)
    if direct is not None:
        return direct
    ref = module.imports.get(name)
    if ref is None:
        return None
    visited = seen if seen is not None else set()
    key = (module.name, name)
    if key in visited:
        return None
    visited.add(key)
    target = _imported_target_module(analysis, module, ref)
    if target is None:
        return None
    target_name = ref.name or name
    found = _class_in_module(target, target_name)
    if found is not None:
        return found
    # ``from pkg import models`` then ``models.Base`` is handled by the caller;
    # here we only follow class re-exports.
    return _find_exported_class(analysis, target, target_name, visited)


def _resolve_class_expr(
    analysis: AnalysisResult,
    current: ModuleInfo | None,
    expr: str,
) -> tuple[ClassInfo | None, str]:
    """Resolve a Python base expression to a local ClassInfo.

    Returns ``(class, confidence)``.  A missing result is not an error: the
    expression may refer to a third-party class outside the analysed project.
    """

    value = _base_expression(ast.parse(expr, mode="eval").body) if expr else ""
    if not value:
        return None, "low"
    parts = value.split(".")
    by_name = {module.name: module for module in analysis.modules}
    if current is not None:
        local = _class_in_module(current, value)
        if local is not None:
            return local, "high"

    # Absolute local module path: app.base.Base or pkg.base.Base.
    for split_at in range(len(parts) - 1, 0, -1):
        module_name = ".".join(parts[:split_at])
        module = by_name.get(module_name)
        found = _class_in_module(module, ".".join(parts[split_at:]))
        if found is not None:
            return found, "high"

    if current is not None:
        head = parts[0]
        ref = current.imports.get(head)
        if ref is not None:
            target = _imported_target_module(analysis, current, ref)
            if target is not None:
                if len(parts) == 1:
                    found = _find_exported_class(analysis, target, ref.name or head)
                    if found is not None:
                        return found, "high"
                else:
                    attr = ".".join(parts[1:])
                    found = _class_in_module(target, attr)
                    if found is not None:
                        return found, "high"
                    # ``from pkg import models`` / ``import pkg.models as models``.
                    candidate_names = []
                    if ref.name:
                        if ref.module:
                            candidate_names.append(f"{ref.module}.{ref.name}")
                        else:
                            resolved_base = _resolve_module_name(current, ref)
                            if resolved_base:
                                candidate_names.append(f"{resolved_base}.{ref.name}")
                    if ref.module:
                        candidate_names.append(ref.module)
                    for candidate_name in candidate_names:
                        candidate_module = by_name.get(candidate_name)
                        found = _class_in_module(candidate_module, attr)
                        if found is not None:
                            return found, "high"
            found = _find_exported_class(analysis, target, ref.name or head)
            if len(parts) > 1 and found is not None:
                # Nested local classes are not stored yet; keep the direct hit
                # only when the attribute names the class itself.
                if _tail(value) == found.name:
                    return found, "medium"

    # Bare name: unique project class by name/qualname.
    matches = [
        cls
        for cls in analysis.classes
        if cls.name == _tail(value) or cls.qualname == value
    ]
    if len(matches) == 1:
        return matches[0], "medium"
    return None, "low"


def _c3_linearize(class_by_id: dict[str, ClassInfo]) -> dict[str, list[str]]:
    """Compute a best-effort C3 MRO over resolved local classes."""

    memo: dict[str, list[str]] = {}
    visiting: set[str] = set()

    def linearize(cid: str) -> list[str]:
        if cid in memo:
            return memo[cid]
        cls = class_by_id[cid]
        bases = [base for base in cls.base_class_ids if base in class_by_id and base != cid]
        if cid in visiting:
            # Cycle: expose the node once and let the validator report it.
            return [cid]
        visiting.add(cid)
        sequences = [list(linearize(base)) for base in bases]
        sequences.append(list(bases))
        merged: list[str] = []
        while any(sequences):
            sequences = [seq for seq in sequences if seq]
            candidate = None
            for seq in sequences:
                head = seq[0]
                if not any(head in other[1:] for other in sequences):
                    candidate = head
                    break
            if candidate is None:
                # Broken/inconsistent hierarchy: deterministic DFS fallback.
                for seq in sequences:
                    for item in seq:
                        if item not in merged:
                            merged.append(item)
                break
            merged.append(candidate)
            for seq in sequences:
                if seq and seq[0] == candidate:
                    seq.pop(0)
        visiting.discard(cid)
        result = [cid, *[item for item in merged if item != cid]]
        memo[cid] = result
        return result

    for cid in sorted(class_by_id):
        linearize(cid)
    return memo


def resolve_type_hierarchy(analysis: AnalysisResult) -> dict[str, list[dict[str, object]]]:
    """Resolve base classes, populate MRO/subclasses and effective abstractness.

    The function mutates language-frontend ``ClassInfo`` records and returns
    structural relation records.  It intentionally ignores standard-library
    and third-party bases while retaining unresolved source names on the class.
    """

    module_by_name = {module.name: module for module in analysis.modules}
    class_by_id = {class_id(cls): cls for cls in analysis.classes}
    relations: list[dict[str, object]] = []

    # Reset derived hierarchy fields in a separate pass. Resolving bases mutates
    # ``target.subclass_ids``; clearing the target later in the same loop would
    # silently erase subclass links for classes that appear after their parent.
    for cls in analysis.classes:
        cls.base_class_ids = []
        cls.unresolved_bases = []
        cls.subclass_ids = []
        cls.mro_class_ids = []
        cls.abstract_method_names = []

    for cls in analysis.classes:
        current = module_by_name.get(cls.module_name)
        seen_bases: set[str] = set()
        for base_node in getattr(cls.node, "bases", []):
            expr = _base_expression(base_node)
            if not expr or _is_external_base(expr):
                continue
            target, confidence = _resolve_class_expr(analysis, current, expr)
            if target is None or target is cls:
                if expr not in cls.unresolved_bases:
                    cls.unresolved_bases.append(expr)
                continue
            target_id = class_id(target)
            if target_id in seen_bases:
                continue
            seen_bases.add(target_id)
            cls.base_class_ids.append(target_id)
            target.subclass_ids.append(class_id(cls))
            kind = "implements" if target.class_kind in {"abstract", "interface"} or target.is_abstract else "inherits"
            relations.append(
                {
                    "id": f"type:{class_id(cls)}:{kind}:{target_id}",
                    "kind": kind,
                    "fromClassId": class_id(cls),
                    "toClassId": target_id,
                    "toClassName": target.qualname,
                    "moduleId": cls.module_id,
                    "targetModuleId": target.module_id,
                    "confidence": confidence,
                    "evidence": {"file": cls.file, "line": cls.line},
                }
            )

    for cls in analysis.classes:
        cls.subclass_ids = sorted(set(cls.subclass_ids))

    mro_by_id = _c3_linearize(class_by_id)
    for cid, cls in class_by_id.items():
        mro = mro_by_id.get(cid, [cid])
        cls.mro_class_ids = mro
        own = {method.name: method for method in cls.methods.values()}
        inherited: dict[str, object] = {}
        for ancestor_id in mro[1:]:
            ancestor = class_by_id[ancestor_id]
            for method in ancestor.methods.values():
                if method.name in own or method.name in inherited:
                    continue
                inherited[method.name] = method
        abstract_names = sorted(
            {
                *(name for name, method in own.items() if getattr(method, "is_abstract", False)),
                *(
                    name
                    for name, method in inherited.items()
                    if getattr(method, "is_abstract", False)
                ),
            }
        )
        was_abstract = bool(cls.is_abstract or cls.class_kind == "abstract")
        is_protocol = cls.class_kind == "interface" or any(
            _tail(base) == "Protocol" for base in cls.bases
        )
        cls.abstract_method_names = abstract_names
        cls.is_abstract = bool(was_abstract or is_protocol or abstract_names)
        if is_protocol:
            cls.class_kind = "interface"
        elif cls.is_abstract:
            cls.class_kind = "abstract"

    return relations
