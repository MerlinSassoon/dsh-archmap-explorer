from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class LanguageFrontend(Protocol):
    """Language adapter contract.

    A frontend owns source discovery, parsing, symbol resolution, module
    projection and canonical FunctionFlow construction. Layout, validation,
    fingerprinting and rendering are intentionally outside this contract.
    """

    language: str
    file_suffixes: tuple[str, ...]

    def analyze(self, project_root: Path, config_path: Path | None = None) -> Any:
        """Return a project analysis object consumable by graph.py.

        The object must expose ``config``, ``modules``, ``functions`` and
        ``diagnostics``. Function records must expose the cross-language fields
        used by the neutral graph layer: id, name, qualname, module_name,
        module_id, file, line, end_line, signature, is_async, note, class_name
        and synthetic.
        """
        ...

    def build_flows(self, analysis: Any) -> list[dict[str, Any]]:
        """Build canonical FunctionFlow dictionaries for every function."""
        ...
