"""Public annotation API.

This facade keeps ``archmap.annotations`` as the stable integration point for
the DSH bridge while the implementation lives in the regular utility layer of
the Python core.
"""

from __future__ import annotations

from .utility.annotation_utility import (
    ANNOTATION_PROMPT_VERSION,
    ANNOTATION_SYSTEM_PROMPT,
    annotation_context,
    apply_annotations,
)

__all__ = [
    "ANNOTATION_PROMPT_VERSION",
    "ANNOTATION_SYSTEM_PROMPT",
    "annotation_context",
    "apply_annotations",
]
