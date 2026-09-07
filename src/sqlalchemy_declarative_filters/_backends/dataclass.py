"""The default backend: a plain :mod:`dataclasses` dataclass, no dependencies.

It is a typed container, not a validator. Nothing checks that the values you put in
match their annotations, and ``@options`` here takes ``dataclasses.field`` keywords
rather than constraints. Use the Pydantic or Marshmallow backend when the values come
from outside your own code and need validating.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from .base import SchemaBackend

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .base import SchemaRequest

__all__ = ("DataclassBackend",)


class DataclassBackend(SchemaBackend):
    """Renders filters as a keyword-only dataclass."""

    name = "dataclass"

    def build(self, request: SchemaRequest) -> type[Any]:
        annotations: dict[str, Any] = {}
        namespace: dict[str, Any] = {
            "__annotations__": annotations,
            "__doc__": request.doc,
            "__module__": request.module,
            "__filters_request__": request,
            "from_mapping": classmethod(_from_mapping),
        }

        for spec in request.specs:
            annotations[spec.name] = spec.schema_annotation
            namespace[spec.name] = _field_for(spec)

        # kw_only keeps declaration order regardless of which filters have defaults.
        return dataclasses.dataclass(kw_only=True)(type(request.name, (), namespace))


def _field_for(spec: Any) -> Any:
    """Build the ``dataclasses.field`` for one filter."""

    options = dict(spec.options)
    metadata = {"description": spec.doc, **options.pop("metadata", {})}

    if "default_factory" in options:
        # A mutable default has to come from a factory; it replaces the plain default.
        return dataclasses.field(metadata=metadata, **options)

    return dataclasses.field(default=spec.schema_default, metadata=metadata, **options)


def _from_mapping(cls: type[Any], data: Mapping[str, Any]) -> Any:
    """Build an instance from a mapping, applying null-string coercion.

    This is what the other backends get from their validation layer. It exists so a
    dataclass schema can still be fed raw query parameters.
    """

    request: SchemaRequest = cls.__filters_request__
    nullable = frozenset(request.nullable_names)
    known = {field.name for field in dataclasses.fields(cls)}
    unknown = set(data) - known

    if unknown:
        names = ", ".join(sorted(unknown))
        raise TypeError(f"{cls.__name__} has no filter(s) named {names}.")

    return cls(
        **{
            name: request.coerce(value) if name in nullable else value
            for name, value in data.items()
        }
    )
