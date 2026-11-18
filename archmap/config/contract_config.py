"""Static contract vocabulary and role constants."""

from __future__ import annotations


EXPOSURE_VALUES = {"public", "internal"}
EXPOSURE_SOURCES = {
    "docstring",
    "comment",
    "decorator",
    "config",
    "entrypoint",
    "protocol",
    "naming",
}
CAPABILITY_KINDS = {
    "function",
    "method",
    "context_manager",
    "async_context_manager",
    "callable",
    "iterable",
}
PROTOCOL_CAPABILITY_KINDS = {
    "context_manager",
    "async_context_manager",
    "callable",
    "iterable",
}

PROVIDER_ROLES = {
    "config",
    "model",
    "manager",
    "adapter",
    "component",
    "contract",
    "utility",
}
PROVIDER_ROLE_ORDER = [
    "config",
    "model",
    "manager",
    "adapter",
    "component",
    "contract",
    "utility",
]
PROVIDER_ROLE_SOURCES = {
    "config",
    "docstring",
    "comment",
    "decorator",
    "entrypoint",
    "structure",
    "naming",
}
# Roles whose public method/protocol capabilities are module developer APIs.
# config/model are type definitions and are projected as type cards instead.
API_EXPOSING_ROLES = PROVIDER_ROLES - {"config", "model", "utility"}
