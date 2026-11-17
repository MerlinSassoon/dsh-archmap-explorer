"""Compatibility shim for the pre-P2.3 discovery module."""

from .frontends.python.discovery_utility import discover_sources
from .model.analysis_model import SourceFile
from .utility.discovery_utility import _assign_module, _matches, _module_name_for

__all__ = ["SourceFile", "_assign_module", "_matches", "discover_sources", "_module_name_for"]
