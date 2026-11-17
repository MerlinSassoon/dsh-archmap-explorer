"""Static database and student-table configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """Connection and table parameters for the local student database."""

    host: str = "localhost"
    user: str = "root"
    database_name: str = "stusys"
    port: int = 3306
    charset: str = "utf8mb4"
    table_name: str = "student_python"
    effective_tables: tuple[str, ...] = ("student_python",)
