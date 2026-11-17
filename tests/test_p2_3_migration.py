from __future__ import annotations

import ast
from pathlib import Path

from archmap.managers.frontend_manager import FrontendManager


REPO_ROOT = Path(__file__).parent.parent
LEGACY_PATHS = [
    "archmap/analysis.py",
    "archmap/callresolver.py",
    "archmap/callsites.py",
    "archmap/cli.py",
    "archmap/config.py",
    "archmap/contracts.py",
    "archmap/details.py",
    "archmap/discover.py",
    "archmap/graph.py",
    "archmap/pipeline.py",
    "archmap/render.py",
    "archmap/validate.py",
    "archmap/frontends/base.py",
    "archmap/frontends/registry.py",
    "archmap/frontends/python/capabilities.py",
    "archmap/frontends/python/roles.py",
]
LEGACY_MODULES = {
    "archmap.analysis",
    "archmap.callresolver",
    "archmap.callsites",
    "archmap.cli",
    "archmap.config",
    "archmap.contracts",
    "archmap.details",
    "archmap.discover",
    "archmap.graph",
    "archmap.pipeline",
    "archmap.render",
    "archmap.validate",
    "archmap.frontends.base",
    "archmap.frontends.registry",
    "archmap.frontends.python.capabilities",
    "archmap.frontends.python.roles",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_legacy_p2_3_shims_are_removed() -> None:
    assert not [path for path in LEGACY_PATHS if (REPO_ROOT / path).exists()]


def test_code_does_not_import_legacy_shims() -> None:
    violations: list[str] = []
    for directory in ("archmap", "tests", "examples"):
        for path in (REPO_ROOT / directory).rglob("*.py"):
            for module in _imported_modules(path):
                if module in LEGACY_MODULES:
                    violations.append(f"{path.relative_to(REPO_ROOT)} -> {module}")
    assert not violations


def test_frontends_package_uses_canonical_frontend_manager() -> None:
    init = (REPO_ROOT / "archmap" / "frontends" / "__init__.py").read_text(encoding="utf-8")
    assert "FRONTENDS" not in init
    assert "get_frontend" not in init
    assert FrontendManager().get("python").language == "python"


def test_console_script_points_at_canonical_entry() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'archmap = "archmap.entry.cli_entry:main"' in pyproject
    assert 'archmap = "archmap.cli:main"' not in pyproject
