"""Python structural relation extraction for P4.

This stage consumes the already-resolved analysis and emits language-neutral
``ClassRelation`` facts for instantiation, type use, aggregation and
composition.  No renderer or impact query should re-parse Python source.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from typing import Iterable

from ...model.analysis_model import AnalysisResult, ClassInfo, FunctionInfo, ModuleInfo
from ...model.call_model import CallSite
from ...model.contract_model import ClassRelation, ProviderRoleInfo
from .type_utility import _resolve_class_expr, class_id


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _annotation_type_exprs(node: ast.AST | None) -> list[str]:
    """Extract candidate class names from a (possibly nested) annotation."""

    if node is None:
        return []
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [_unparse(node)]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Subscript):
        return [*_annotation_type_exprs(node.value), *_annotation_type_exprs(node.slice)]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [item for element in node.elts for item in _annotation_type_exprs(element)]
    if isinstance(node, ast.BinOp):
        return [*_annotation_type_exprs(node.left), *_annotation_type_exprs(node.right)]
    return []


def _walk_scope(node: ast.AST) -> Iterable[ast.AST]:
    """Yield nodes in one function/class scope without entering nested scopes."""

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield child
        yield from _walk_scope(child)


def _resolve_annotation_class(
    analysis: AnalysisResult,
    module: ModuleInfo | None,
    node: ast.AST | None,
    *,
    owner: ClassInfo,
) -> ClassInfo | None:
    for expr in _annotation_type_exprs(node):
        found, _confidence = _resolve_class_expr(analysis, module, expr)
        if found is not None and class_id(found) != class_id(owner):
            return found
    return None


def _relation(
    owner: ClassInfo,
    target: ClassInfo,
    kind: str,
    *,
    source: str,
    confidence: str,
    function: FunctionInfo | None = None,
    line: int | None = None,
) -> ClassRelation:
    owner_id = class_id(owner)
    target_id = class_id(target)
    return ClassRelation(
        id=f"type:{owner_id}:{kind}:{target_id}",
        kind=kind,
        from_class_id=owner_id,
        to_class_id=target_id,
        to_class_name=target.qualname,
        module_id=owner.module_id,
        target_module_id=target.module_id,
        confidence=confidence,
        evidence_file=function.file if function is not None else owner.file,
        evidence_line=line or (function.line if function is not None else owner.line),
        from_provider_id=owner_id,
        to_provider_id=target_id,
        source=source,
        evidence_function_ids=[function.id] if function is not None else [],
    )


def _merge_relations(relations: list[ClassRelation]) -> list[ClassRelation]:
    grouped: dict[tuple[str, str, str], ClassRelation] = {}
    rank = {"low": 0, "medium": 1, "high": 2}
    for relation in relations:
        key = (relation.from_class_id, relation.kind, relation.to_class_id)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = relation
            continue
        if rank.get(relation.confidence, 0) > rank.get(existing.confidence, 0):
            existing.confidence = relation.confidence
        existing.evidence_function_ids = sorted(
            set(existing.evidence_function_ids) | set(relation.evidence_function_ids)
        )
    return sorted(grouped.values(), key=lambda item: (item.module_id, item.from_class_id, item.kind, item.to_class_id))


def extract_structural_relations(
    analysis: AnalysisResult,
    call_sites: Iterable[CallSite] | None = None,
    provider_roles: dict[str, ProviderRoleInfo] | None = None,
) -> list[ClassRelation]:
    """Extract `instantiates` / `uses` / `aggregates` / `composes` facts."""

    module_by_name = {module.name: module for module in analysis.modules}
    relations: list[ClassRelation] = []
    del call_sites  # CallSite remains the behavioral fact source; AST is used here for type context.

    for owner in analysis.classes:
        module = module_by_name.get(owner.module_name)
        owner_id = class_id(owner)

        # Field declarations: A has a typed field B and therefore uses/aggregates B.
        for stmt in owner.node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            target = _resolve_annotation_class(analysis, module, stmt.annotation, owner=owner)
            if target is None:
                continue
            relations.append(
                _relation(owner, target, "uses", source="field_annotation", confidence="high", line=stmt.lineno)
            )
            relations.append(
                _relation(owner, target, "aggregates", source="field_annotation", confidence="medium", line=stmt.lineno)
            )

        init = owner.methods.get("__init__")
        assigned_params: set[str] = set()
        if init is not None:
            for node in _walk_scope(init.node):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    value = node.value
                    if not isinstance(value, ast.Name):
                        continue
                    for target_node in targets:
                        if (
                            isinstance(target_node, ast.Attribute)
                            and isinstance(target_node.value, ast.Name)
                            and target_node.value.id == "self"
                        ):
                            assigned_params.add(value.id)

        for fn in owner.methods.values():
            # Type annotations on method arguments and return values.
            annotation_nodes: list[ast.AST] = []
            for arg in (
                list(getattr(fn.node.args, "posonlyargs", []))
                + list(fn.node.args.args)
                + list(fn.node.args.kwonlyargs)
            ):
                if arg.annotation is not None:
                    annotation_nodes.append(arg.annotation)
            vararg = getattr(fn.node.args, "vararg", None)
            kwarg = getattr(fn.node.args, "kwarg", None)
            if vararg is not None and vararg.annotation is not None:
                annotation_nodes.append(vararg.annotation)
            if kwarg is not None and kwarg.annotation is not None:
                annotation_nodes.append(kwarg.annotation)
            if getattr(fn.node, "returns", None) is not None:
                annotation_nodes.append(fn.node.returns)
            for annotation in annotation_nodes:
                target = _resolve_annotation_class(analysis, module, annotation, owner=owner)
                if target is not None:
                    relations.append(
                        _relation(
                            owner,
                            target,
                            "uses",
                            source="type_annotation",
                            confidence="high",
                            function=fn,
                            line=getattr(annotation, "lineno", fn.line),
                        )
                    )

            # Constructor-injected aggregate: def __init__(self, repo: Repo) and
            # self.repo = repo.
            if fn.name == "__init__":
                for arg in list(fn.node.args.args) + list(fn.node.args.kwonlyargs):
                    if arg.arg not in assigned_params or arg.annotation is None:
                        continue
                    target = _resolve_annotation_class(analysis, module, arg.annotation, owner=owner)
                    if target is not None:
                        relations.append(
                            _relation(
                                owner,
                                target,
                                "aggregates",
                                source="constructor_injection",
                                confidence="high",
                                function=fn,
                                line=getattr(arg.annotation, "lineno", fn.line),
                            )
                        )

            # Instantiation and ownership.
            for node in _walk_scope(fn.node):
                if not isinstance(node, ast.Call):
                    continue
                called_expr = _unparse(node.func)
                target, _confidence = _resolve_class_expr(analysis, module, called_expr)
                if target is None or class_id(target) == owner_id:
                    continue
                relations.append(
                    _relation(
                        owner,
                        target,
                        "instantiates",
                        source="constructor_call",
                        confidence="high",
                        function=fn,
                        line=node.lineno,
                    )
                )

                # A composition is an owned instance created in the constructor
                # and stored on self.  Other factory/create calls remain
                # `instantiates` only.
                if fn.name not in {"__init__", "__post_init__"}:
                    continue
                for assign in _walk_scope(fn.node):
                    if not isinstance(assign, ast.Assign) or assign.value is not node:
                        continue
                    if any(
                        isinstance(target_node, ast.Attribute)
                        and isinstance(target_node.value, ast.Name)
                        and target_node.value.id == "self"
                        for target_node in assign.targets
                    ):
                        relations.append(
                            _relation(
                                owner,
                                target,
                                "composes",
                                source="constructor_assignment",
                                confidence="high",
                                function=fn,
                                line=assign.lineno,
                            )
                        )

    merged = _merge_relations(relations)
    roles = provider_roles or {}
    for relation in merged:
        from_info = roles.get(relation.from_class_id)
        to_info = roles.get(relation.to_class_id)
        relation.from_provider_role = from_info.role if from_info else None
        relation.to_provider_role = to_info.role if to_info else None
        relation.from_visibility = from_info.provider_visibility if from_info else None
        relation.to_visibility = to_info.provider_visibility if to_info else None
    return merged
