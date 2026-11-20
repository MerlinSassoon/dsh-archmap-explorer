"""Command-line entry point for the task board demo."""

import sys

from .config import AppConfig, load_config
from .models import Priority, TaskError
from .report import ReportBuilder
from .service import TaskService
from .storage import JsonTaskStore

USAGE = """taskboard <command> [options]

commands:
  add <title> [--high]   add a task
  done <id>              mark a task as done
  list [--open]          list tasks
  stats                  print counters
"""


def build_service(config: AppConfig) -> TaskService:
    """Wire the storage adapter into the service."""
    return TaskService(JsonTaskStore(config.data_file))


def parse_args(argv: list[str]) -> tuple[str, list[str]]:
    """Split the command name from its arguments."""
    if not argv:
        return "help", []
    return argv[0], argv[1:]


def main(argv: list[str] | None = None) -> int:
    """Run one command and return the process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    command, rest = parse_args(arguments)
    if command in ("help", "--help", "-h"):
        print(USAGE)
        return 0

    config = load_config("--verbose" in rest)
    service = build_service(config)
    report = ReportBuilder(config.page_size)

    try:
        if command == "add":
            title = " ".join(arg for arg in rest if not arg.startswith("--"))
            priority = Priority.HIGH if "--high" in rest else Priority.NORMAL
            task = service.add(title, priority, [])
            print(f"added {task.label()}")
        elif command == "done":
            task = service.complete(int(rest[0]))
            print(f"closed {task.label()}")
        elif command == "list":
            tasks = service.select("--open" in rest)
            print(report.render(tasks, 1))
        elif command == "stats":
            print(report.summary(service.stats()))
        else:
            print(f"unknown command: {command}")
            print(USAGE)
            return 2
    except (TaskError, ValueError, IndexError) as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
