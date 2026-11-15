from __future__ import annotations

from .base import LanguageFrontend
from .python import PythonFrontend


FRONTENDS: dict[str, LanguageFrontend] = {
    "python": PythonFrontend(),
}


def get_frontend(language: str) -> LanguageFrontend:
    try:
        return FRONTENDS[language]
    except KeyError:
        supported = ", ".join(sorted(FRONTENDS))
        raise ValueError(f"unsupported language {language!r}; available: {supported}") from None
