"""Compatibility shim for the pre-P2.3 CLI module."""

from .entry.cli_entry import main
from .utility.cli_utility import (
    build_parser,
    cmd_build,
    cmd_check,
    cmd_diff,
    cmd_method,
    cmd_serve,
)

__all__ = [
    "build_parser",
    "cmd_build",
    "cmd_check",
    "cmd_diff",
    "cmd_method",
    "cmd_serve",
    "main",
]
