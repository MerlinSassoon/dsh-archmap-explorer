"""Compatibility shim for language frontend registration."""

from ..managers.frontend_manager import FrontendManager

_MANAGER = FrontendManager()
FRONTENDS = _MANAGER.frontends


def get_frontend(language: str):
    return _MANAGER.get(language)


__all__ = ["FRONTENDS", "get_frontend"]
