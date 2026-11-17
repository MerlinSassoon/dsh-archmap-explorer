"""Compatibility shim for the pre-P2.3 analysis module."""

from .frontends.python.analysis_utility import analyze_project
from .model.analysis_model import AnalysisResult, ClassInfo, FunctionInfo, ImportRef, ModuleInfo, SourceFile
from .utility.analysis_utility import ENTRY_METHOD_NAMES
from .utility.call_utility import BUILTIN_NAMES

__all__ = [
    "AnalysisResult",
    "BUILTIN_NAMES",
    "ClassInfo",
    "ENTRY_METHOD_NAMES",
    "FunctionInfo",
    "ImportRef",
    "ModuleInfo",
    "SourceFile",
    "analyze_project",
]
