"""Graph projection facade manager."""

from __future__ import annotations

from typing import Any, Iterable

from ..model.analysis_model import AnalysisResult
from ..model.call_model import CallSite
from ..model.contract_model import ContractModel
from ..utility.graph_utility import build_bundle, semantic_fingerprint


class GraphManager:
    """Facade for ProjectGraph/ModuleGraph projection.

    Entrypoints, call aggregation and fingerprint helpers remain internal
    utility operations; consumers use this manager facade.
    """

    def build_bundle(
        self,
        analysis: AnalysisResult,
        call_sites: Iterable[CallSite],
        function_details: list[dict[str, Any]],
        contract_model: ContractModel | None = None,
    ) -> dict[str, Any]:
        return build_bundle(analysis, call_sites, function_details, contract_model)

    def semantic_fingerprint(self, bundle: dict[str, Any]) -> str:
        return semantic_fingerprint(bundle)
