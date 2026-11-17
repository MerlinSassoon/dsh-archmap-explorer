"""Student record and table-shape model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STUDENT_COLUMNS: tuple[str, ...] = (
    "sno",
    "sname",
    "ssex",
    "sbirthday",
    "speciality",
    "tc",
)

STUDENT_COLUMN_WIDTHS: tuple[int, ...] = (8, 8, 6, 12, 12, 6)


@dataclass(frozen=True)
class StudentRecord:
    """A single student row used by the sample table renderer."""

    sno: str
    sname: str
    ssex: str
    sbirthday: str
    speciality: str
    tc: int

    def as_row(self) -> tuple[Any, ...]:
        return (
            self.sno,
            self.sname,
            self.ssex,
            self.sbirthday,
            self.speciality,
            self.tc,
        )
