"""Domain models for the task board demo."""

from dataclasses import dataclass, field
from enum import Enum


class Priority(Enum):
    """Ordering hint attached to a task."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TaskError(Exception):
    """Raised when a task operation cannot be completed."""


@dataclass
class Task:
    """A single task entry."""

    task_id: int
    title: str
    priority: Priority = Priority.NORMAL
    done: bool = False
    tags: list[str] = field(default_factory=list)

    def label(self) -> str:
        """Render the task as one terminal line."""
        mark = "x" if self.done else " "
        return f"[{mark}] #{self.task_id} {self.title} ({self.priority.value})"
