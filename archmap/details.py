"""Compatibility shim for the pre-P2.3 detail module."""

from .frontends.python.detail_utility import build_function_details
from .utility.detail_utility import (
    _callee_entry,
    _caller_entry,
    _json_hash,
    _owner_class_id,
    _raises,
    _source_slice,
    _unparse,
)

__all__ = [
    "_callee_entry",
    "_caller_entry",
    "_json_hash",
    "_owner_class_id",
    "_raises",
    "_source_slice",
    "_unparse",
    "build_function_details",
]
