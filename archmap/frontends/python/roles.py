"""Compatibility shim for Python provider-role inference."""

from .role_utility import build_provider_roles
from ...utility.role_utility import (
    _configured_role,
    _infer_class_role,
    _infer_function_role,
    _metadata_role,
    _type_summary,
)

__all__ = [
    "_configured_role",
    "_infer_class_role",
    "_infer_function_role",
    "_metadata_role",
    "_type_summary",
    "build_provider_roles",
]
