"""Standalone student-table rendering verification script."""

from __future__ import annotations

from ..model.student_model import STUDENT_COLUMNS, STUDENT_COLUMN_WIDTHS, StudentRecord
from ..utility.display_utility import write_table


def print_students(students: list[StudentRecord]) -> int:
    """打印学生信息表格"""
    rows = [student.as_row() for student in students]
    return write_table(rows, STUDENT_COLUMNS, STUDENT_COLUMN_WIDTHS)


def main() -> None:
    students = [
        StudentRecord(
            sno="191002",
            sname="张慧玲",
            ssex="女",
            sbirthday="1999-11-07",
            speciality="计算机",
            tc=50,
        )
    ]
    print_students(students)


if __name__ == "__main__":
    main()
