"""Declarative SQLAlchemy filters and sorting with auto-generated schemas.

Import ``Filters``, ``Sorting`` and the decorators from this package for the
dependency-free dataclass backend, or from ``.pydantic`` / ``.marshmallow`` for those.
The names are the same in all three, so switching a project over is a one-line change::

    from sqlalchemy_declarative_filters.pydantic import Filters, Sorting, options, skip_null
"""

from __future__ import annotations

from ._decorators import deprecated, descending, options, skip_null
from ._exceptions import (
    BackendNotAvailableError,
    FilterConditionError,
    FilterDeclarationError,
    FilterError,
    InvalidOrderError,
    JoinConflictWarning,
    RedundantSkipNullWarning,
    UnknownFilterError,
    UnknownSortError,
)
from ._joins import Statement
from ._meta import Filters, FiltersMeta
from ._params import Params, ParamsMeta
from ._sorting import PRIMARY_KEY, OrderStyle, Sorting, SortingMeta

__version__ = "0.3.0"

#: Explicit alias, for when more than one backend's base is in the same module.
DataclassFilters = Filters
DataclassSorting = Sorting
DataclassParams = Params

__all__ = (
    "PRIMARY_KEY",
    "BackendNotAvailableError",
    "DataclassFilters",
    "DataclassParams",
    "DataclassSorting",
    "FilterConditionError",
    "FilterDeclarationError",
    "FilterError",
    "Filters",
    "FiltersMeta",
    "InvalidOrderError",
    "JoinConflictWarning",
    "OrderStyle",
    "Params",
    "ParamsMeta",
    "RedundantSkipNullWarning",
    "Sorting",
    "SortingMeta",
    "Statement",
    "UnknownFilterError",
    "UnknownSortError",
    "__version__",
    "deprecated",
    "descending",
    "options",
    "skip_null",
)
