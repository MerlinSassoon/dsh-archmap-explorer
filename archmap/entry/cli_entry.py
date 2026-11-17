"""CLI process entry point."""

from __future__ import annotations

import argparse

from ..utility.cli_utility import build_parser


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
