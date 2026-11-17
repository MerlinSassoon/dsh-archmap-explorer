"""Compatibility shim for the pre-P2.3 call resolver module."""

from .frontends.python.call_utility import CallResolver
from .model.call_model import ResolvedCall
from .utility.call_utility import _annotation_name

__all__ = ["CallResolver", "ResolvedCall", "_annotation_name"]
