"""Filters whose generated schema is a Marshmallow schema.

Same names as the top-level package, so only the import line changes::

    from sqlalchemy_declarative_filters.marshmallow import Filters, options, skip_null

``options`` keywords are :class:`marshmallow.fields.Field` keywords here, so
constraints are expressed with ``validate=...``.

Marshmallow's ``load()`` returns a plain dict, which ``apply`` takes directly::

    statement = BookFilters.apply(statement, BookFilters.Schema().load(params))

Needs the ``marshmallow`` extra:
``pip install sqlalchemy-declarative-filters[marshmallow]``.
"""

from __future__ import annotations

from typing import Generic

from ._backends import get_backend
from ._decorators import deprecated, descending, options, skip_null
from ._joins import Statement
from ._meta import Filters as _Filters
from ._meta import FiltersMeta, ModelT
from ._sorting import OrderStyle, SortingMeta
from ._sorting import Sorting as _Sorting

# Fail here, with an installation hint, rather than at first schema access.
get_backend("marshmallow")

__all__ = (
    "Filters",
    "MarshmallowFilters",
    "MarshmallowFiltersMeta",
    "MarshmallowSorting",
    "MarshmallowSortingMeta",
    "OrderStyle",
    "Sorting",
    "Statement",
    "deprecated",
    "descending",
    "options",
    "skip_null",
)


class MarshmallowFiltersMeta(FiltersMeta):
    """Metaclass of :class:`MarshmallowFilters`; narrows the schema types for checkers."""


class MarshmallowFilters(_Filters[ModelT], Generic[ModelT], metaclass=MarshmallowFiltersMeta):
    """Base class whose ``Schema`` is a :class:`marshmallow.Schema` subclass."""

    __backend__ = "marshmallow"


#: The name to inherit from; ``MarshmallowFilters`` is the unambiguous alias.
Filters = MarshmallowFilters


class MarshmallowSortingMeta(SortingMeta):
    """Metaclass of :class:`MarshmallowSorting`; narrows the schema types for checkers."""


class MarshmallowSorting(_Sorting[ModelT], Generic[ModelT], metaclass=MarshmallowSortingMeta):
    """Base class for sorting whose ``Schema`` is a :class:`marshmallow.Schema` subclass."""

    __backend__ = "marshmallow"


#: The name to inherit from; ``MarshmallowSorting`` is the unambiguous alias.
Sorting = MarshmallowSorting
