"""Compatibility shim — import from memory.organizational_memory instead.

This module will be removed in v2.0. Update your imports:
    from memory.organizational_memory import OrgMemory
"""

import warnings

from memory.organizational_memory import *  # noqa: F401, F403
from memory.organizational_memory import _DEFAULT_CHROMA_PATH, OrgMemory  # noqa: F401

warnings.warn(
    "memory.organisational_memory is deprecated. "
    "Use memory.organizational_memory instead. "
    "This shim will be removed in v2.0.",
    DeprecationWarning,
    stacklevel=2,
)
