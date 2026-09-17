"""Public typing surface for the dataclass namespace.

The implementation modules stay plain, annotated Python and are type-checked as such;
only the three namespace modules carry stubs, because their signatures are the part
that differs per backend and reads badly inline.
"""

from collections.abc import Callable, Mapping
from dataclasses import Field
from enum import Enum
from typing import Any, ClassVar, Generic, TypeAlias, overload

from sqlalchemy.sql._typing import (
    _ColumnExpressionArgument,
    _ColumnExpressionOrStrLabelArgument,
    _JoinTargetArgument,
    _OnClauseArgument,
)
from sqlalchemy.sql.dml import UpdateBase
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Exists, Select
from typing_extensions import Self, TypeVar

from ._spec import FilterSpec as FilterSpec
from ._spec import SortSpec as SortSpec

__version__: str

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])

#: What a filters class filters, when it says: ``class BookFilters(Filters[Book])``.
#: Left open, it is ``Any``, and ``apply`` takes any statement as it always has.
_ModelT = TypeVar("_ModelT", default=Any)

#: The statements that are not a select of the model, and so are not checked against
#: it: an Exists to narrow, an UPDATE or DELETE to filter the rows of.
_OtherStatementT = TypeVar("_OtherStatementT", bound=Exists | UpdateBase)

class _GeneratedSchemaMeta(type):
    #: Whatever the backend puts on the schema class: ``model_fields``, ``opts``, ...
    def __getattr__(cls, name: str) -> Any: ...

class _GeneratedSchema(metaclass=_GeneratedSchemaMeta):
    """A generated schema, as a type checker sees it.

    The fields come from the filter methods and are built at runtime, so no stub can
    name them. Declared as a class rather than as a ``type[Any]`` property, so that
    ``BookFilters.Schema`` is a valid annotation -- which is how it reaches FastAPI --
    and its fields can be read off an instance without a checker objecting.
    """

    def __init__(self, **values: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...

class _DataclassSchema(_GeneratedSchema):
    """The dataclass backend's schema: a keyword-only dataclass."""

    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]
    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Self:
        """Build an instance from raw values, mapping null-like strings to ``None``."""

class FilterError(Exception): ...
class FilterDeclarationError(FilterError, TypeError): ...
class UnknownFilterError(FilterError, KeyError): ...
class UnknownSortError(FilterError, KeyError): ...
class InvalidOrderError(FilterError, ValueError): ...
class BackendNotAvailableError(FilterError, ImportError): ...
class JoinConflictWarning(UserWarning): ...
class RedundantSkipNullWarning(UserWarning): ...

class FiltersMeta(type):
    # The schemas are declared on the classes themselves, as nested classes, because
    # that is the only form a type checker takes as an annotation.
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
    #: The generated schema, in whichever backend ``__backend__`` names. A class, so
    #: that it works as an annotation: ``Annotated[BookFilters.Schema, Query()]``.
    class Schema(_DataclassSchema): ...
    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    #: The same filters in one named backend, whatever ``__backend__`` says. Only the
    #: backend of this namespace is spelled out; the other two are, in theirs.
    Dataclass: TypeAlias = Schema
    Pydantic: TypeAlias = _GeneratedSchema
    Marshmallow: TypeAlias = _GeneratedSchema
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

#: The default ``__tiebreaker__`` of a sorting class: its model's primary key.
PRIMARY_KEY: Any

class OrderStyle(str, Enum):
    """How the caller spells the direction of a sort."""

    CODE = "code"
    ASC_FLAG = "asc_flag"
    DESC_FLAG = "desc_flag"
    PREFIX = "prefix"

class SortingMeta(type):
    @property
    def __sorts__(cls) -> tuple[SortSpec, ...]: ...
    #: What the class sorts: its type parameter, or its own ``__model__``.
    @property
    def __model__(cls) -> Any: ...
    def build_schema(cls, backend: str | None = ...) -> type[Any]: ...

class Sorting(Statement, Generic[_ModelT], metaclass=SortingMeta):
    #: The generated schema, in whichever backend ``__backend__`` names. A class, so
    #: that it works as an annotation: ``Annotated[BookSorting.Schema, Query()]``.
    class Schema(_DataclassSchema): ...
    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    #: The same sort field in one named backend, whatever ``__backend__`` says. Only the
    #: backend of this namespace is spelled out; the other two are, in theirs.
    Dataclass: TypeAlias = Schema
    Pydantic: TypeAlias = _GeneratedSchema
    Marshmallow: TypeAlias = _GeneratedSchema
    #: Which backend ``Schema`` uses; set by the base class you inherit from.
    __backend__: str
    #: Overrides the generated schema's class name.
    __schema_name__: str
    #: What the class sorts, when the type parameter is not how you want to say it.
    __model__: ClassVar[Any]
    #: The name of the field that picks the sort.
    __sort_field__: ClassVar[str]
    #: The name of the field that picks the direction; ``None`` names it after the style.
    __order_field__: ClassVar[str | None]
    #: How the direction is spelled.
    __order_style__: ClassVar[OrderStyle]
    #: The sort applied when the caller chooses none.
    __default_sort__: ClassVar[str | None]
    #: Keys appended after every sort: the primary key by default, or ``None``.
    __tiebreaker__: ClassVar[Any]

    # Spelled out here rather than on Statement, where it would stop filters from
    # being named order_by. A sort cannot be, so nothing is lost.
    def order_by(
        self,
        *clauses: _ColumnExpressionOrStrLabelArgument[Any] | None,
    ) -> Statement:
        """``Select.order_by``, with each key reversed when the caller asked for desc."""

    # Really a method of the metaclass; declared here so that the class's own type
    # parameter is in scope, which is what makes the statement checkable against it.
    @classmethod
    def apply(
        cls,
        statement: Select[tuple[_ModelT]],
        values: Mapping[str, Any] | Any | None = ...,
    ) -> Select[tuple[_ModelT]]: ...
    @classmethod
    def statement(
        cls,
        values: Mapping[str, Any] | Any | None = ...,
    ) -> Select[tuple[_ModelT]]:
        """``apply(select(model), values)``, for a plain select of the model."""

DataclassSorting = Sorting

class ParamsMeta(type):
    #: The filters and sorting classes combined, by attribute name.
    @property
    def __parts__(cls) -> dict[str, FiltersMeta | SortingMeta]: ...
    #: What the class lists: its type parameter, or its own ``__model__``.
    @property
    def __model__(cls) -> Any: ...
    def build_schema(cls, backend: str | None = ...) -> type[Any]: ...

class Params(Generic[_ModelT], metaclass=ParamsMeta):
    #: The generated schema, in whichever backend ``__backend__`` names. A class, so
    #: that it works as an annotation: ``Annotated[BookParams.Schema, Query()]``.
    class Schema(_DataclassSchema): ...
    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    #: The same parts' fields in one named backend, whatever ``__backend__`` says. Only the
    #: backend of this namespace is spelled out; the other two are, in theirs.
    Dataclass: TypeAlias = Schema
    Pydantic: TypeAlias = _GeneratedSchema
    Marshmallow: TypeAlias = _GeneratedSchema
    #: Which backend ``Schema`` uses; set by the base class you inherit from.
    __backend__: str
    #: Overrides the generated schema's class name.
    __schema_name__: str
    #: What the class lists, when the type parameter is not how you want to say it.
    __model__: ClassVar[Any]

    # Really a method of the metaclass; declared here so that the class's own type
    # parameter is in scope, which is what makes the statement checkable against it.
    @classmethod
    def apply(
        cls,
        statement: Select[tuple[_ModelT]],
        values: Mapping[str, Any] | Any | None = ...,
    ) -> Select[tuple[_ModelT]]:
        """Every filters part, then the sorting part, applied to ``statement``."""

    @classmethod
    def statement(
        cls,
        values: Mapping[str, Any] | Any | None = ...,
    ) -> Select[tuple[_ModelT]]:
        """``apply(select(model), values)``, for a plain select of the model."""

DataclassParams = Params

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
def descending(func: _FuncT) -> _FuncT:
    """Make a sort run descending when the caller does not say which way."""
