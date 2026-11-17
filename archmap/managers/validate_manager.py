"""Bundle validation facade manager."""

from __future__ import annotations

from typing import Any

from ..utility.validate_utility import validate_bundle


class ValidationManager:
    """Facade for architecture bundle validation."""

    def validate(self, bundle: dict[str, Any]) -> list[dict[str, Any]]:
        return validate_bundle(bundle)
