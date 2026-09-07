"""Public typing surface for the Pydantic namespace."""

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue

from . import Filters as _DataclassFilters
from . import FiltersMeta
from . import Statement as Statement

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])

class PydanticFiltersMeta(FiltersMeta):
    @property
    def Schema(cls) -> type[BaseModel]: ...
    @property
    def Model(cls) -> type[BaseModel]: ...
    @property
    def Pydantic(cls) -> type[BaseModel]: ...

class PydanticFilters(_DataclassFilters, metaclass=PydanticFiltersMeta): ...

Filters = PydanticFilters

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

def skip_null(func: _FuncT) -> _FuncT: ...
