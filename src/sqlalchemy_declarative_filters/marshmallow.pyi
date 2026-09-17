"""Public typing surface for the Marshmallow namespace."""

from collections.abc import Callable, Iterable, Mapping
from typing import Any, Generic, TypeAlias, overload

from marshmallow import Schema as _MarshmallowSchema
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
_Validator = Callable[[Any], Any]

class _MarshmallowGeneratedSchema(_MarshmallowSchema):
    """A generated Marshmallow schema, as a type checker sees it.

    The fields are built at runtime from the declarations; everything
    :class:`marshmallow.Schema` declares -- ``load`` above all -- keeps its own type.
    """

class MarshmallowFiltersMeta(FiltersMeta): ...

class MarshmallowFilters(
    _DataclassFilters[_ModelT],
    Generic[_ModelT],
    metaclass=MarshmallowFiltersMeta,
):
    #: A class, so that it works as an annotation; the values it loads --
    #: ``BookFilters.Schema().load(params)`` -- go straight to ``apply``.
    class Schema(_MarshmallowGeneratedSchema): ...
    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    Marshmallow: TypeAlias = Schema

Filters = MarshmallowFilters

class MarshmallowSortingMeta(SortingMeta): ...

class MarshmallowSorting(
    _DataclassSorting[_ModelT],
    Generic[_ModelT],
    metaclass=MarshmallowSortingMeta,
):
    #: A class, so that it works as an annotation; the values it loads --
    #: ``BookSorting.Schema().load(params)`` -- go straight to ``apply``.
    class Schema(_MarshmallowGeneratedSchema): ...
    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    Marshmallow: TypeAlias = Schema

Sorting = MarshmallowSorting

class MarshmallowParamsMeta(ParamsMeta): ...

class MarshmallowParams(
    _DataclassParams[_ModelT],
    Generic[_ModelT],
    metaclass=MarshmallowParamsMeta,
):
    #: A class, so that it works as an annotation; the values it loads --
    #: ``BookParams.Schema().load(params)`` -- go straight to ``apply``.
    class Schema(_MarshmallowGeneratedSchema): ...
    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model: TypeAlias = Schema
    Marshmallow: TypeAlias = Schema

Params = MarshmallowParams

def options(
    *,
    load_default: Any = ...,
    dump_default: Any = ...,
    attribute: str | None = ...,
    data_key: str | None = ...,
    validate: _Validator | Iterable[_Validator] | None = ...,
    required: bool = ...,
    allow_none: bool | None = ...,
    load_only: bool = ...,
    dump_only: bool = ...,
    error_messages: Mapping[str, str] | None = ...,
    metadata: Mapping[str, Any] = ...,
) -> Callable[[_FuncT], _FuncT]:
    """Keywords for :class:`marshmallow.fields.Field`, which is what backs this namespace.

    Constraints go through ``validate``: ``@options(validate=validate.Length(min=3))``.
    """

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
