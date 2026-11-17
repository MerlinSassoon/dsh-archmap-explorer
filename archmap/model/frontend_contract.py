"""Language frontend protocol contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class LanguageFrontend(Protocol):
    """Language adapter contract.

    A frontend owns source discovery, parsing, symbol resolution, call-site
    extraction and function-detail construction.  Macro layout, validation,
    fingerprinting and rendering are outside this contract.
    """

    language: str
    file_suffixes: tuple[str, ...]

    def analyze(self, project_root: Path, config_path: Path | None = None) -> Any:
        """Return a project analysis object consumable by graph.py.

        The object must expose ``config``, ``modules``, ``functions``,
        ``classes`` and ``diagnostics``. Function records must expose the
        cross-language fields used by the neutral graph layer: id, name,
        qualname, module_name, module_id, file, line, end_line, signature,
        is_async, note, class_name, method_kind, visibility, is_abstract and
        synthetic.
        """
        ...

    def build_call_sites(self, analysis: Any) -> list[Any]:
        """Return canonical call-site records for all analyzed functions."""
        ...

    def build_function_details(
        self, analysis: Any, call_sites: list[Any]
    ) -> list[dict[str, Any]]:
        """Build source-backed detail records for every function/method."""
        ...

    def build_contracts(self, analysis: Any, call_sites: Any = None) -> Any:
        """Build the language-neutral API contract projection.

        The result must be an ``archmap.contracts.ContractModel``.  Frontends
        own language-specific exposure tags, naming rules, Provider Role
        inference, type summaries and protocol detection; graph.py only
        consumes canonical capabilities and role metadata.
        """
        ...
