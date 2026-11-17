"""Compatibility shim for the pre-P2.3 config module."""

from .config.project_config import (
    DEFAULT_EXCLUDES,
    DEFAULT_INTERNAL_API_TAGS,
    DEFAULT_PUBLIC_API_TAGS,
    MODULE_ROLES,
    ModuleConfig,
    ProjectConfig,
)
from .utility.config_utility import load_config

__all__ = [
    "DEFAULT_EXCLUDES",
    "DEFAULT_INTERNAL_API_TAGS",
    "DEFAULT_PUBLIC_API_TAGS",
    "MODULE_ROLES",
    "ModuleConfig",
    "ProjectConfig",
    "load_config",
]
