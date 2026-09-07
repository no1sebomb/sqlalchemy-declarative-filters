"""Public typing surface for the dataclass namespace.

The implementation modules stay plain, annotated Python and are type-checked as such;
only the three namespace modules carry stubs, because their signatures are the part
that differs per backend and reads badly inline.
"""

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from sqlalchemy.sql._typing import (
    _ColumnExpressionArgument,
    _JoinTargetArgument,
    _OnClauseArgument,
)
from sqlalchemy.sql.selectable import Select

from ._spec import FilterSpec as FilterSpec

__version__: str

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])
_StatementT = TypeVar("_StatementT")

class FilterError(Exception): ...
class FilterDeclarationError(FilterError, TypeError): ...
class UnknownFilterError(FilterError, KeyError): ...
class BackendNotAvailableError(FilterError, ImportError): ...
class JoinConflictWarning(UserWarning): ...

class FiltersMeta(type):
    #: The generated schema, in whichever backend ``__backend__`` names.
    @property
    def Schema(cls) -> type[Any]: ...
    #: Alias of :attr:`Schema`.
    @property
    def Model(cls) -> type[Any]: ...
    @property
    def Dataclass(cls) -> type[Any]: ...
    @property
    def Pydantic(cls) -> type[Any]: ...
    @property
    def Marshmallow(cls) -> type[Any]: ...
    @property
    def __filters__(cls) -> tuple[FilterSpec, ...]: ...
    def build_schema(cls, backend: str | None = ...) -> type[Any]: ...
    def apply(
        cls,
        statement: _StatementT,
        values: Mapping[str, Any] | Any | None = ...,
    ) -> _StatementT: ...

class Statement:
    """The statement being built, as a filter body sees it.

    ``self`` inside a filter is one of these, and so is what a filter returns.
    Everything a SQLAlchemy ``Select`` offers is forwarded. Only the handful of methods
    a filter body genuinely needs are spelled out, because every name declared here is
    a name a filter cannot have; ``__getattr__`` covers ``order_by``, ``distinct`` and
    the rest of the statement's surface.
    """

    def where(self, *whereclause: _ColumnExpressionArgument[bool]) -> Statement: ...
    def having(self, *having: _ColumnExpressionArgument[bool]) -> Statement: ...
    def join(
        self,
        target: _JoinTargetArgument,
        onclause: _OnClauseArgument | None = ...,
        *,
        isouter: bool = ...,
        full: bool = ...,
    ) -> Statement:
        """Join ``target`` unless it is already joined.

        Deduplicated against the joins the other filters in the same ``apply`` asked
        for and against the ones the incoming statement already carried.
        """

    def outerjoin(
        self,
        target: _JoinTargetArgument,
        onclause: _OnClauseArgument | None = ...,
        *,
        full: bool = ...,
    ) -> Statement: ...
    #: The underlying SQLAlchemy statement.
    def unwrap(self) -> Select[Any]: ...
    def __getattr__(self, name: str) -> Any: ...

class Filters(Statement, metaclass=FiltersMeta):
    #: Which backend ``Schema`` uses; set by the base class you inherit from.
    __backend__: str
    #: Strings a query parameter may use to mean ``null`` on a ``@skip_null`` filter.
    __null_strings__: frozenset[str]
    #: Overrides the generated schema's class name.
    __schema_name__: str

DataclassFilters = Filters

def options(
    *,
    default_factory: Callable[[], Any] = ...,
    init: bool = ...,
    repr: bool = ...,
    hash: bool | None = ...,
    compare: bool = ...,
    metadata: Mapping[str, Any] = ...,
    kw_only: bool = ...,
) -> Callable[[_FuncT], _FuncT]:
    """Keywords for :func:`dataclasses.field`, which is what backs this namespace."""

def skip_null(func: _FuncT) -> _FuncT: ...
