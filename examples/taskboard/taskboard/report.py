"""Terminal rendering for task lists."""

from .models import Task


class ReportBuilder:
    """Turns task lists and counters into terminal text."""

    def __init__(self, page_size: int):
        self.page_size = page_size

    def summary(self, stats: dict[str, int]) -> str:
        """Render the counters shown by the stats command."""
        open_count = stats.get("open", 0)
        done_count = stats.get("done", 0)
        high_count = stats.get("high", 0)
        return f"open={open_count} done={done_count} high={high_count}"

    def render(self, tasks: list[Task], page: int) -> str:
        """Render one page of tasks, newest ids last."""
        start = (page - 1) * self.page_size
        window = tasks[start : start + self.page_size]
        if not window:
            return "(no tasks on this page)"
        return "\n".join(task.label() for task in window)
