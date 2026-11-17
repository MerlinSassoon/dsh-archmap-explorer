"""Graph projection helper models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallRecord:
    from_function: str
    to_function: str
    from_module: str
    to_module: str
    file: str
    line: int
    has_data: bool
    external: bool = False
