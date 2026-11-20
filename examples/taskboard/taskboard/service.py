"""Task operations: add, complete, list and search."""

from .models import Priority, Task, TaskError
from .storage import JsonTaskStore


class TaskService:
    """Owns the in-memory board and delegates persistence to the store."""

    def __init__(self, store: JsonTaskStore):
        self.store = store
        self.tasks: list[Task] = []
        self._next_id = 1
        self._reload()

    def _reload(self) -> None:
        """Load the board and continue ids after the largest existing one."""
        self.tasks = self.store.load()
        if self.tasks:
            self._next_id = max(task.task_id for task in self.tasks) + 1

    def add(self, title: str, priority: Priority, tags: list[str]) -> Task:
        """Append a new task and persist the board."""
        task = Task(task_id=self._next_id, title=title, priority=priority, tags=tags)
        self._next_id += 1
        self.tasks.append(task)
        self.store.save(self.tasks)
        return task

    def complete(self, task_id: int) -> Task:
        """Mark one task as done; raise TaskError when it does not exist."""
        for task in self.tasks:
            if task.task_id == task_id:
                task.done = True
                self.store.save(self.tasks)
                return task
        raise TaskError(f"no task with id {task_id}")

    def select(self, only_open: bool) -> list[Task]:
        """Filter the board, keeping open tasks when asked."""
        if only_open:
            return [task for task in self.tasks if not task.done]
        return list(self.tasks)

    def stats(self) -> dict[str, int]:
        """Count tasks per priority plus the number still open."""
        counts: dict[str, int] = {"open": 0, "done": 0}
        for task in self.tasks:
            if task.done:
                counts["done"] += 1
            else:
                counts["open"] += 1
            counts[task.priority.value] = counts.get(task.priority.value, 0) + 1
        return counts
