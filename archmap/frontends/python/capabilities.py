"""Compatibility shim for Python capability construction."""

from .contract_utility import build_capabilities
from ...utility.contract_utility import (
    _capability,
    _constructor_display,
    _format_params,
    _function_capability,
    _protocol_capabilities,
    _unparse,
)

__all__ = [
    "_capability",
    "_constructor_display",
    "_format_params",
    "_function_capability",
    "_protocol_capabilities",
    "_unparse",
    "build_capabilities",
]
