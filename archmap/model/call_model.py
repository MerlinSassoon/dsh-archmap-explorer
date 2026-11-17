"""Canonical call-site and resolved-call models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolvedCall:
    name: str
    qualified_name: str = ""
    target_function_id: str | None = None
    resolved: bool = False
    external: bool = False
    recursive: bool = False
    confidence: str = "low"
    candidates: list[str] = field(default_factory=list)
    polymorphic: bool = False
    dispatch_kind: str = "static"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "qualifiedName": self.qualified_name,
            "targetFunctionId": self.target_function_id,
            "resolved": self.resolved,
            "external": self.external,
            "recursive": self.recursive,
            "confidence": self.confidence,
            "candidates": list(self.candidates),
            "polymorphic": self.polymorphic,
            "dispatchKind": self.dispatch_kind,
        }
@dataclass
class CallSite:
    """A single static call site discovered inside a function or method."""

    id: str
    from_function_id: str
    from_module_id: str
    to_function_id: str | None
    to_module_id: str | None
    file: str
    line: int
    column: int
    callee_text: str
    call_text: str
    kind: str
    resolved: bool
    external: bool
    recursive: bool
    confidence: str
    candidates: list[str] = field(default_factory=list)
    argument_count: int = 0
    polymorphic: bool = False
    dispatch_kind: str = "static"
    usage_kind: str = "call"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fromFunctionId": self.from_function_id,
            "fromModuleId": self.from_module_id,
            "toFunctionId": self.to_function_id,
            "toModuleId": self.to_module_id,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "calleeText": self.callee_text,
            "callText": self.call_text,
            "kind": self.kind,
            "resolved": self.resolved,
            "external": self.external,
            "recursive": self.recursive,
            "confidence": self.confidence,
            "candidates": list(self.candidates),
            "argumentCount": self.argument_count,
            "polymorphic": self.polymorphic,
            "dispatchKind": self.dispatch_kind,
            "usageKind": self.usage_kind,
        }
