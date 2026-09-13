"""Public typing surface for the dataclass namespace.

The implementation modules stay plain, annotated Python and are type-checked as such;
only the three namespace modules carry stubs, because their signatures are the part
that differs per backend and reads badly inline.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar, Generic, overload

from sqlalchemy.sql._typing import (
    _ColumnExpressionArgument,
    _JoinTargetArgument,
    _OnClauseArgument,
)
from sqlalchemy.sql.dml import UpdateBase
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Exists, Select
from typing_extensions import TypeVar

from ._spec import FilterSpec as FilterSpec

__version__: str

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])

#: What a filters class filters, when it says: ``class BookFilters(Filters[Book])``.
#: Left open, it is ``Any``, and ``apply`` takes any statement as it always has.
_ModelT = TypeVar("_ModelT", default=Any)

#: The statements that are not a select of the model, and so are not checked against
#: it: an Exists to narrow, an UPDATE or DELETE to filter the rows of.
_OtherStatementT = TypeVar("_OtherStatementT", bound=Exists | UpdateBase)

class FilterError(Exception): ...
class FilterDeclarationError(FilterError, TypeError): ...
class UnknownFilterError(FilterError, KeyError): ...
class BackendNotAvailableError(FilterError, ImportError): ...
class JoinConflictWarning(UserWarning): ...
class RedundantSkipNullWarning(UserWarning): ...

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
    #: What the class filters: its type parameter, or its own ``__model__``.
    @property
    def __model__(cls) -> Any: ...
    def build_schema(cls, backend: str | None = ...) -> type[Any]: ...

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

class Filters(Statement, Generic[_ModelT], metaclass=FiltersMeta):
    #: Which backend ``Schema`` uses; set by the base class you inherit from.
    __backend__: str
    #: Strings a query parameter may use to mean ``null`` on a ``@skip_null`` filter.
    __null_strings__: frozenset[str]
    #: Overrides the generated schema's class name.
    __schema_name__: str
    #: What the class filters, when the type parameter is not how you want to say it.
    __model__: ClassVar[Any]

    # Really a method of the metaclass; declared here so that the class's own type
    # parameter is in scope, which is what makes the statement checkable against it.
    @overload
    @classmethod
    def apply(
        cls,
        statement: Select[tuple[_ModelT]],
        values: Mapping[str, Any] | Any | None = ...,
    ) -> Select[tuple[_ModelT]]: ...
    @overload
    @classmethod
    def apply(
        cls,
        statement: _OtherStatementT,
        values: Mapping[str, Any] | Any | None = ...,
    ) -> _OtherStatementT: ...
    @classmethod
    def statement(
        cls,
        values: Mapping[str, Any] | Any | None = ...,
    ) -> Select[tuple[_ModelT]]:
        """``apply(select(model), values)``, for a plain select of the model."""

    @classmethod
    def condition(
        cls,
        values: Mapping[str, Any] | Any | None = ...,
    ) -> ColumnElement[bool]:
        """The filters as one WHERE clause, ``true()`` when none of them apply."""

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

@overload
def deprecated(reason: _FuncT, /) -> _FuncT: ...
@overload
def deprecated(
    reason: str | None = ...,
    /,
    *,
    alternative: str | None = ...,
) -> Callable[[_FuncT], _FuncT]:
    """Flag the filter as deprecated in the generated schema."""

def skip_null(func: _FuncT) -> _FuncT: ...
