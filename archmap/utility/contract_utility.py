"""Provider capability synthesis helpers."""

from __future__ import annotations

import ast

from ..model.analysis_model import AnalysisResult, ClassInfo, FunctionInfo
from ..model.contract_model import ApiCapability, ClassUsage, ProviderRoleInfo


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _format_params(fn: FunctionInfo | None, *, drop_first: bool = False) -> str:
    if fn is None:
        return ""
    node = fn.node
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    args = node.args
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for index, (arg, default) in enumerate(zip(positional, defaults)):
        if drop_first and index == 0 and arg.arg in {"self", "cls"}:
            continue
        text = arg.arg
        if arg.annotation is not None:
            text += f": {_unparse(arg.annotation)}"
        if default is not None:
            text += f"={_unparse(default)}"
        parts.append(text)
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        if drop_first and arg.arg in {"self", "cls"} and not parts:
            continue
        text = arg.arg
        if arg.annotation is not None:
            text += f": {_unparse(arg.annotation)}"
        if default is not None:
            text += f"={_unparse(default)}"
        parts.append(text)
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return ", ".join(parts)


def _constructor_display(cls: ClassInfo) -> str:
    init = cls.methods.get("__init__")
    return f"{cls.name}({_format_params(init, drop_first=True)})"


def _capability(
    *,
    capability_id: str,
    kind: str,
    display: str,
    signature: str,
    provider_id: str,
    provider_kind: str,
    provider_name: str,
    module_id: str,
    exposure: str,
    exposure_source: str,
    exposure_confidence: str,
    function_id: str | None = None,
    evidence_function_ids: list[str] | None = None,
    constructor_function_id: str | None = None,
    note: str = "",
    file: str = "",
    line: int = 0,
    end_line: int = 0,
    role_info: ProviderRoleInfo | None = None,
    inherited: bool = False,
    declared_in_provider_id: str | None = None,
    inherited_from_provider_id: str | None = None,
    overrides_capability_id: str | None = None,
    inherited_from_class_ids: list[str] | None = None,
) -> ApiCapability:
    return ApiCapability(
        id=capability_id,
        kind=kind,
        display=display,
        signature=signature,
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_name=provider_name,
        module_id=module_id,
        exposure=exposure,
        exposure_source=exposure_source,
        exposure_confidence=exposure_confidence,
        function_id=function_id,
        evidence_function_ids=list(evidence_function_ids or []),
        constructor_function_id=constructor_function_id,
        note=note,
        file=file,
        line=line,
        end_line=end_line,
        provider_role=role_info.role if role_info else "utility",
        role_source=role_info.role_source if role_info else "structure",
        role_confidence=role_info.role_confidence if role_info else "medium",
        provider_visibility=role_info.provider_visibility if role_info else "internal",
        owner_provider_id=role_info.owner_provider_id if role_info else None,
        inherited=inherited,
        declared_in_provider_id=declared_in_provider_id or provider_id,
        inherited_from_provider_id=inherited_from_provider_id,
        overrides_capability_id=overrides_capability_id,
        inherited_from_class_ids=list(inherited_from_class_ids or []),
    )


def _protocol_capabilities(
    cls: ClassInfo, role_info: ProviderRoleInfo | None = None
) -> tuple[list[ApiCapability], list[str]]:
    methods = cls.methods
    class_id = f"cls:{cls.module_name}.{cls.qualname}"
    init = methods.get("__init__")
    constructor_id = init.id if init else None
    constructor_text = _constructor_display(cls)
    capabilities: list[ApiCapability] = []
    protocols: list[str] = []
    base_evidence = [constructor_id] if constructor_id else []

    def add(kind: str, display: str, evidence: list[str]) -> None:
        protocols.append(kind)
        capabilities.append(
            _capability(
                capability_id=f"api:{class_id}:{kind}",
                kind=kind,
                display=display,
                signature=display,
                provider_id=class_id,
                provider_kind="class",
                provider_name=cls.name,
                module_id=cls.module_id,
                exposure="public",
                exposure_source="protocol",
                exposure_confidence="high",
                evidence_function_ids=[item for item in [*base_evidence, *evidence] if item],
                constructor_function_id=constructor_id,
                note=cls.note,
                file=cls.file,
                line=cls.line,
                end_line=cls.end_line,
                role_info=role_info,
                declared_in_provider_id=class_id,
            )
        )

    if "__enter__" in methods and "__exit__" in methods:
        add(
            "context_manager",
            f"with {constructor_text}",
            [methods["__enter__"].id, methods["__exit__"].id],
        )
    if "__aenter__" in methods and "__aexit__" in methods:
        add(
            "async_context_manager",
            f"async with {constructor_text}",
            [methods["__aenter__"].id, methods["__aexit__"].id],
        )
    if "__call__" in methods:
        add("callable", constructor_text, [methods["__call__"].id])
    if "__iter__" in methods:
        add("iterable", f"for item in {constructor_text}", [methods["__iter__"].id])
    return capabilities, protocols


def _function_capability(
    fn: FunctionInfo, role_info: ProviderRoleInfo | None = None
) -> ApiCapability:
    kind = "method" if fn.class_name else "function"
    owner_name = fn.class_name.split(".")[-1] if fn.class_name else fn.name
    params = _format_params(fn, drop_first=bool(fn.class_name))
    display = f"{owner_name}.{fn.name}({params})" if fn.class_name else f"{fn.name}({params})"
    provider_id = f"cls:{fn.module_name}.{fn.class_name}" if fn.class_name else fn.id
    provider_kind = "class" if fn.class_name else "function"
    provider_name = owner_name if fn.class_name else fn.name
    return _capability(
        capability_id=f"api:{fn.id}",
        kind=kind,
        display=display,
        signature=fn.signature,
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_name=provider_name,
        module_id=fn.module_id,
        exposure=fn.api_exposure,
        exposure_source=fn.api_exposure_source,
        exposure_confidence=fn.api_exposure_confidence,
        function_id=fn.id,
        evidence_function_ids=[fn.id],
        note=fn.note,
        file=fn.file,
        line=fn.line,
        end_line=fn.end_line,
        role_info=role_info,
        declared_in_provider_id=provider_id,
    )
