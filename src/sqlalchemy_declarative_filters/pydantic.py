"""Filters whose generated schema is a Pydantic model.

Same names as the top-level package, so only the import line changes::

    from sqlalchemy_declarative_filters.pydantic import Filters, options, skip_null

``options`` keywords are :func:`pydantic.Field` keywords here.

Needs the ``pydantic`` extra: ``pip install sqlalchemy-declarative-filters[pydantic]``.
"""

from __future__ import annotations

from ._backends import get_backend
from ._decorators import options, skip_null
from ._joins import Statement
from ._meta import Filters as _Filters
from ._meta import FiltersMeta

# Fail here, with an installation hint, rather than at first schema access.
get_backend("pydantic")

__all__ = (
    "Filters",
    "PydanticFilters",
    "PydanticFiltersMeta",
    "Statement",
    "options",
    "skip_null",
)


class PydanticFiltersMeta(FiltersMeta):
    """Metaclass of :class:`PydanticFilters`; narrows the schema types for checkers."""


class PydanticFilters(_Filters, metaclass=PydanticFiltersMeta):
    """Base class whose ``Schema`` is a :class:`pydantic.BaseModel` subclass."""

    __backend__ = "pydantic"


#: The name to inherit from; ``PydanticFilters`` is the unambiguous alias.
Filters = PydanticFilters
