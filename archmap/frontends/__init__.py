from __future__ import annotations

from .base import LanguageFrontend


def __getattr__(name: str):
    if name in {"FRONTENDS", "get_frontend"}:
        from ..managers.frontend_manager import FrontendManager

        manager = FrontendManager()
        return {"FRONTENDS": manager.frontends, "get_frontend": manager.get}[name]
    raise AttributeError(name)


__all__ = ["LanguageFrontend", "FRONTENDS", "get_frontend"]
