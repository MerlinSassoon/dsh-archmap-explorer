"""Configuration package exports."""

from .contract_config import (
    API_EXPOSING_ROLES,
    CAPABILITY_KINDS,
    EXPOSURE_SOURCES,
    EXPOSURE_VALUES,
    PROVIDER_ROLE_ORDER,
    PROVIDER_ROLE_SOURCES,
    PROVIDER_ROLES,
)
from .project_config import (
    DEFAULT_EXCLUDES,
    DEFAULT_INTERNAL_API_TAGS,
    DEFAULT_PUBLIC_API_TAGS,
    MODULE_ROLES,
    ModuleConfig,
    ProjectConfig,
)

__all__ = [
    "API_EXPOSING_ROLES",
    "CAPABILITY_KINDS",
    "DEFAULT_EXCLUDES",
    "DEFAULT_INTERNAL_API_TAGS",
    "DEFAULT_PUBLIC_API_TAGS",
    "EXPOSURE_SOURCES",
    "EXPOSURE_VALUES",
    "MODULE_ROLES",
    "ModuleConfig",
    "PROVIDER_ROLE_ORDER",
    "PROVIDER_ROLE_SOURCES",
    "PROVIDER_ROLES",
    "ProjectConfig",
]


def __getattr__(name: str):
    if name == "load_config":
        from ..utility.config_utility import load_config

        return load_config
    raise AttributeError(name)
