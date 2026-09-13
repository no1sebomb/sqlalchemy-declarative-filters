"""Declarative SQLAlchemy filters with auto-generated schemas.

Import ``Filters`` and the decorators from this package for the dependency-free
dataclass backend, or from ``.pydantic`` / ``.marshmallow`` for those. The names are
the same in all three, so switching a project over is a one-line change::

    from sqlalchemy_declarative_filters.pydantic import Filters, options, skip_null
"""

from __future__ import annotations

from ._decorators import deprecated, options, skip_null
from ._exceptions import (
    BackendNotAvailableError,
    FilterConditionError,
    FilterDeclarationError,
    FilterError,
    JoinConflictWarning,
    RedundantSkipNullWarning,
    UnknownFilterError,
)
from ._joins import Statement
from ._meta import Filters, FiltersMeta

__version__ = "0.1.0"

#: Explicit alias, for when more than one backend's base is in the same module.
DataclassFilters = Filters

__all__ = (
    "BackendNotAvailableError",
    "DataclassFilters",
    "FilterConditionError",
    "FilterDeclarationError",
    "FilterError",
    "Filters",
    "FiltersMeta",
    "JoinConflictWarning",
    "RedundantSkipNullWarning",
    "Statement",
    "UnknownFilterError",
    "__version__",
    "deprecated",
    "options",
    "skip_null",
)
