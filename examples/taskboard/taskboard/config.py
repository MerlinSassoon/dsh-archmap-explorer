"""Static configuration for the task board demo."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings resolved before the command runs."""

    data_file: str = "tasks.json"
    page_size: int = 10
    verbose: bool = False

    def describe(self) -> str:
        """Return the one-line banner shown by the CLI."""
        mode = "verbose" if self.verbose else "quiet"
        return f"{self.data_file} | page {self.page_size} | {mode}"


def load_config(verbose: bool = False) -> AppConfig:
    """Build the default configuration, optionally in verbose mode."""
    return AppConfig(verbose=verbose)
