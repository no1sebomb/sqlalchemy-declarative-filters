"""Public typing surface for the Pydantic namespace."""

from collections.abc import Callable
from typing import Any, Generic, TypeAlias, overload

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue
from typing_extensions import TypeVar

from . import PRIMARY_KEY as PRIMARY_KEY
from . import Filters as _DataclassFilters
from . import FiltersMeta, ParamsMeta, SortingMeta
from . import OrderStyle as OrderStyle
from . import Params as _DataclassParams
from . import Sorting as _DataclassSorting
from . import Statement as Statement

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])
_ModelT = TypeVar("_ModelT", default=Any)

class _PydanticSchema(BaseModel):
    """A generated Pydantic model, as a type checker sees it.

    The fields are built at runtime from the declarations, so ``__getattr__`` stands
    in for them; everything :class:`~pydantic.BaseModel` declares keeps its own type.
    Every ``Schema`` below repeats ``__init__`` because a checker builds one from the
    fields a Pydantic model declares, and a stub can declare none of them.
    """

    def __init__(self, **values: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...

class PydanticFiltersMeta(FiltersMeta): ...

class PydanticFilters(
    _DataclassFilters[_ModelT],
    Generic[_ModelT],
    metaclass=PydanticFiltersMeta,
):
    #: A class, so that it works as an annotation, which is how FastAPI reads it:
    #: ``Annotated[BookFilters.Schema, Query()]``.
    class Schema(_PydanticSchema):
        def __init__(self, **values: Any) -> None: ...

    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    Pydantic: TypeAlias = Schema

Filters = PydanticFilters

class PydanticSortingMeta(SortingMeta): ...

class PydanticSorting(
    _DataclassSorting[_ModelT],
    Generic[_ModelT],
    metaclass=PydanticSortingMeta,
):
    #: A class, so that it works as an annotation, which is how FastAPI reads it:
    #: ``Annotated[BookSorting.Schema, Query()]``.
    class Schema(_PydanticSchema):
        def __init__(self, **values: Any) -> None: ...

    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    Pydantic: TypeAlias = Schema

Sorting = PydanticSorting

class PydanticParamsMeta(ParamsMeta): ...

class PydanticParams(
    _DataclassParams[_ModelT],
    Generic[_ModelT],
    metaclass=PydanticParamsMeta,
):
    #: A class, so that it works as an annotation, which is how FastAPI reads it:
    #: ``Annotated[BookParams.Schema, Query()]``.
    class Schema(_PydanticSchema):
        def __init__(self, **values: Any) -> None: ...

    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    Pydantic: TypeAlias = Schema

Params = PydanticParams

def options(
    *,
    default_factory: Callable[[], Any] = ...,
    alias: str | None = ...,
    validation_alias: str | None = ...,
    serialization_alias: str | None = ...,
    title: str | None = ...,
    description: str | None = ...,
    examples: list[Any] | None = ...,
    exclude: bool | None = ...,
    discriminator: str | None = ...,
    frozen: bool | None = ...,
    validate_default: bool | None = ...,
    repr: bool = ...,
    init_var: bool | None = ...,
    kw_only: bool | None = ...,
    pattern: str | None = ...,
    strict: bool | None = ...,
    gt: float | None = ...,
    ge: float | None = ...,
    lt: float | None = ...,
    le: float | None = ...,
    multiple_of: float | None = ...,
    allow_inf_nan: bool | None = ...,
    max_digits: int | None = ...,
    decimal_places: int | None = ...,
    min_length: int | None = ...,
    max_length: int | None = ...,
    union_mode: str = ...,
    json_schema_extra: JsonSchemaValue | Callable[[JsonSchemaValue], None] | None = ...,
) -> Callable[[_FuncT], _FuncT]:
    """Keywords for :func:`pydantic.Field`, which is what backs this namespace."""

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
