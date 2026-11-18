"""Wire-protocol data model shared by client and server commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProtocolMessage:
    """JSON message envelope sent between the menu client and database server."""

    model: int
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "args": list(self.args),
            "kwargs": dict(self.kwargs),
        }
