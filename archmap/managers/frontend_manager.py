"""Frontend registry manager."""

from __future__ import annotations

from ..frontends.python.python_manager import PythonFrontend
from ..model.frontend_contract import LanguageFrontend


class FrontendManager:
    """Owns language-frontend instances and resolves them by language name."""

    def __init__(self) -> None:
        self.frontends: dict[str, LanguageFrontend] = {
            "python": PythonFrontend(),
        }

    def get(self, language: str) -> LanguageFrontend:
        try:
            return self.frontends[language]
        except KeyError:
            supported = ", ".join(sorted(self.frontends))
            raise ValueError(
                f"unsupported language {language!r}; available: {supported}"
            ) from None
