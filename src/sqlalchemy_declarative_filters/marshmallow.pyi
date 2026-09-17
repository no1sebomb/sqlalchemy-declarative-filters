"""Public typing surface for the Marshmallow namespace."""

from collections.abc import Callable, Iterable, Mapping
from typing import Any, Generic, overload

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

class MarshmallowFiltersMeta(FiltersMeta):
    @property
    def Schema(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Model(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Marshmallow(cls) -> type[_MarshmallowSchema]: ...

class MarshmallowFilters(
    _DataclassFilters[_ModelT],
    Generic[_ModelT],
    metaclass=MarshmallowFiltersMeta,
): ...

Filters = MarshmallowFilters

class MarshmallowSortingMeta(SortingMeta):
    @property
    def Schema(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Model(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Marshmallow(cls) -> type[_MarshmallowSchema]: ...

class MarshmallowSorting(
    _DataclassSorting[_ModelT],
    Generic[_ModelT],
    metaclass=MarshmallowSortingMeta,
): ...

Sorting = MarshmallowSorting

class MarshmallowParamsMeta(ParamsMeta):
    @property
    def Schema(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Model(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Marshmallow(cls) -> type[_MarshmallowSchema]: ...

class MarshmallowParams(
    _DataclassParams[_ModelT],
    Generic[_ModelT],
    metaclass=MarshmallowParamsMeta,
): ...

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
