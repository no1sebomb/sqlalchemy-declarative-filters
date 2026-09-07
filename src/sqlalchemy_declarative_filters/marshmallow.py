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

from ._backends import get_backend
from ._decorators import options, skip_null
from ._joins import Statement
from ._meta import Filters as _Filters
from ._meta import FiltersMeta

# Fail here, with an installation hint, rather than at first schema access.
get_backend("marshmallow")

__all__ = (
    "Filters",
    "MarshmallowFilters",
    "MarshmallowFiltersMeta",
    "Statement",
    "options",
    "skip_null",
)


class MarshmallowFiltersMeta(FiltersMeta):
    """Metaclass of :class:`MarshmallowFilters`; narrows the schema types for checkers."""


class MarshmallowFilters(_Filters, metaclass=MarshmallowFiltersMeta):
    """Base class whose ``Schema`` is a :class:`marshmallow.Schema` subclass."""

    __backend__ = "marshmallow"


#: The name to inherit from; ``MarshmallowFilters`` is the unambiguous alias.
Filters = MarshmallowFilters
