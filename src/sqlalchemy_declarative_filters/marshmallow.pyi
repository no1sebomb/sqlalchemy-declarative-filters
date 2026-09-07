"""Public typing surface for the Marshmallow namespace."""

from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeVar

from marshmallow import Schema as _MarshmallowSchema

from . import Filters as _DataclassFilters
from . import FiltersMeta
from . import Statement as Statement

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])
_Validator = Callable[[Any], Any]

class MarshmallowFiltersMeta(FiltersMeta):
    @property
    def Schema(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Model(cls) -> type[_MarshmallowSchema]: ...
    @property
    def Marshmallow(cls) -> type[_MarshmallowSchema]: ...

class MarshmallowFilters(_DataclassFilters, metaclass=MarshmallowFiltersMeta): ...

Filters = MarshmallowFilters

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

def skip_null(func: _FuncT) -> _FuncT: ...
