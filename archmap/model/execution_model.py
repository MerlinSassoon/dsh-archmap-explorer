"""Canonical bounded execution-flow models for P5."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionNode:
    """One semantic execution node.

    Execution nodes are deliberately bounded: free functions and functional
    interfaces are opaque call steps, while only entrypoint control structures
    are expanded into branch/loop nodes.
    """

    id: str
    kind: str
    label: str
    module_id: str
    order: int
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "moduleId": self.module_id,
            "order": self.order,
            **self.data,
        }


@dataclass
class ExecutionEdge:
    """One execution/control edge between execution nodes."""

    id: str
    from_node: str
    to_node: str
    kind: str
    label: str = ""
    confidence: str = "high"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from": self.from_node,
            "to": self.to_node,
            "kind": self.kind,
            "label": self.label,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            **self.data,
        }


@dataclass
class ExecutionFlow:
    """One entrypoint-centric bounded execution flow."""

    id: str
    module_id: str
    entrypoint_id: str
    entrypoint_reason: str
    name: str
    nodes: list[ExecutionNode]
    edges: list[ExecutionEdge]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "archmap.execution-flow",
            "id": self.id,
            "moduleId": self.module_id,
            "entrypointId": self.entrypoint_id,
            "entrypointReason": self.entrypoint_reason,
            "name": self.name,
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
            "nodeCount": len(self.nodes),
            "edgeCount": len(self.edges),
            "truncated": self.truncated,
            "diagnostics": list(self.diagnostics),
            "layout": self.layout,
        }
