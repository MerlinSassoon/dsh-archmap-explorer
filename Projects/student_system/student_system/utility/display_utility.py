"""Terminal display helpers owned by the menu component."""

from __future__ import annotations

import sys
import unicodedata
from typing import Any, Iterable, Sequence


def get_display_width(text: str) -> int:
    """Return terminal display width: CJK/fullwidth characters count as two."""

    width = 0
    for char in str(text):
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W", "A") else 1
    return width


def write_table(
    rows: Iterable[Sequence[Any]],
    columns: Sequence[str],
    widths: Sequence[int],
) -> int:
    """Write a fixed-width table and return its total line count."""

    materialized = list(rows)
    if not materialized:
        return 0
    border = "+" + "+".join("-" * width for width in widths) + "+\n"
    sys.stdout.write(border)
    sys.stdout.write("|")
    for index, header in enumerate(columns):
        sys.stdout.write(f"{header:<{widths[index]}}|")
    sys.stdout.write("\n")
    sys.stdout.write(border)
    for row in materialized:
        sys.stdout.write("|")
        for index, cell in enumerate(row):
            padding = widths[index] - get_display_width(str(cell))
            sys.stdout.write(f"{cell}{' ' * padding}|")
        sys.stdout.write("\n")
    sys.stdout.write(border)
    sys.stdout.flush()
    return len(materialized) + 4
