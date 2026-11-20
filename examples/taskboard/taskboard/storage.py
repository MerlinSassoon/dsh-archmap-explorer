"""Persistence for tasks: a small JSON-file adapter."""

import json
from pathlib import Path

from .models import Priority, Task


class JsonTaskStore:
    """Store tasks in a single JSON file next to the working directory."""

    def __init__(self, path: str):
        self.path = Path(path)

    def load(self) -> list[Task]:
        """Read every task from disk; a missing file means an empty board."""
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        tasks: list[Task] = []
        for item in raw.get("tasks", []):
            tasks.append(
                Task(
                    task_id=int(item["task_id"]),
                    title=str(item["title"]),
                    priority=Priority(item.get("priority", "normal")),
                    done=bool(item.get("done", False)),
                    tags=[str(tag) for tag in item.get("tags", [])],
                )
            )
        return tasks

    def save(self, tasks: list[Task]) -> None:
        """Write every task back to disk."""
        payload = {
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "priority": task.priority.value,
                    "done": task.done,
                    "tags": task.tags,
                }
                for task in tasks
            ]
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
