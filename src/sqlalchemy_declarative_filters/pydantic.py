"""Filters whose generated schema is a Pydantic model.

Same names as the top-level package, so only the import line changes::

    from sqlalchemy_declarative_filters.pydantic import Filters, options, skip_null

``options`` keywords are :func:`pydantic.Field` keywords here.

Needs the ``pydantic`` extra: ``pip install sqlalchemy-declarative-filters[pydantic]``.
"""

from __future__ import annotations

from typing import Generic

from ._backends import get_backend
from ._decorators import deprecated, descending, options, skip_null
from ._joins import Statement
from ._meta import Filters as _Filters
from ._meta import FiltersMeta, ModelT
from ._params import Params as _Params
from ._params import ParamsMeta
from ._sorting import PRIMARY_KEY, OrderStyle, SortingMeta
from ._sorting import Sorting as _Sorting

# Fail here, with an installation hint, rather than at first schema access.
get_backend("pydantic")

__all__ = (
    "PRIMARY_KEY",
    "Filters",
    "OrderStyle",
    "Params",
    "PydanticFilters",
    "PydanticFiltersMeta",
    "PydanticParams",
    "PydanticParamsMeta",
    "PydanticSorting",
    "PydanticSortingMeta",
    "Sorting",
    "Statement",
    "deprecated",
    "descending",
    "options",
    "skip_null",
)


class PydanticFiltersMeta(FiltersMeta):
    """Metaclass of :class:`PydanticFilters`; narrows the schema types for checkers."""


class PydanticFilters(_Filters[ModelT], Generic[ModelT], metaclass=PydanticFiltersMeta):
    """Base class whose ``Schema`` is a :class:`pydantic.BaseModel` subclass."""

    __backend__ = "pydantic"


#: The name to inherit from; ``PydanticFilters`` is the unambiguous alias.
Filters = PydanticFilters


class PydanticSortingMeta(SortingMeta):
    """Metaclass of :class:`PydanticSorting`; narrows the schema types for checkers."""


class PydanticSorting(_Sorting[ModelT], Generic[ModelT], metaclass=PydanticSortingMeta):
    """Base class for sorting whose ``Schema`` is a :class:`pydantic.BaseModel` subclass."""

    __backend__ = "pydantic"


#: The name to inherit from; ``PydanticSorting`` is the unambiguous alias.
Sorting = PydanticSorting


class PydanticParamsMeta(ParamsMeta):
    """Metaclass of :class:`PydanticParams`; narrows the schema types for checkers."""


class PydanticParams(_Params[ModelT], Generic[ModelT], metaclass=PydanticParamsMeta):
    """Base class for combined params whose ``Schema`` is a :class:`pydantic.BaseModel`."""

    __backend__ = "pydantic"


#: The name to inherit from; ``PydanticParams`` is the unambiguous alias.
Params = PydanticParams
