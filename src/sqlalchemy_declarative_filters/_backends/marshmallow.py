"""The Marshmallow backend: a ``Schema`` subclass whose ``load()`` returns a dict.

Marshmallow has no single field class, so annotations are mapped onto concrete field
types here. ``@options`` keywords go to that field's constructor -- ``validate``,
``data_key``, ``required`` and the rest -- and constraints are expressed the
Marshmallow way, with validators::

    @options(validate=validate.Length(min=3))
    def name(self, value: str): ...
"""

from __future__ import annotations

import datetime
import decimal
import enum
import uuid
from typing import TYPE_CHECKING, Any, Literal, get_args, get_origin

from marshmallow import EXCLUDE, Schema, fields, pre_load, validate

from .._spec import unwrap_optional
from .base import SchemaBackend

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .._spec import FilterSpec
    from .base import SchemaRequest

__all__ = ("MarshmallowBackend",)

_SCALARS: dict[Any, type[fields.Field[Any]]] = {
    str: fields.String,
    int: fields.Integer,
    float: fields.Float,
    bool: fields.Boolean,
    decimal.Decimal: fields.Decimal,
    datetime.datetime: fields.DateTime,
    datetime.date: fields.Date,
    datetime.time: fields.Time,
    datetime.timedelta: fields.TimeDelta,
    uuid.UUID: fields.UUID,
    dict: fields.Dict,
}

_SEQUENCES = (list, set, frozenset, tuple)


class MarshmallowBackend(SchemaBackend):
    """Renders filters as a Marshmallow schema."""

    name = "marshmallow"
    extra = "marshmallow"

    def build(self, request: SchemaRequest) -> type[Schema]:
        namespace: dict[str, Any] = {
            "__doc__": request.doc,
            "__module__": request.module,
            # Filters are optional by nature; an unknown one is a caller mistake.
            "Meta": type("Meta", (), {"unknown": EXCLUDE}),
        }

        for spec in request.specs:
            namespace[spec.name] = _field_for(spec)

        if request.nullable_names:
            namespace["_coerce_null_strings"] = pre_load(_coercer(request))

        return type(request.name, (Schema,), namespace)


def _field_for(spec: FilterSpec) -> fields.Field[Any]:
    """Build the Marshmallow field for one filter."""

    options: dict[str, Any] = {
        "allow_none": spec.optional,
        "load_default": spec.schema_default,
        "metadata": {"description": spec.doc},
        **spec.options,
    }

    return _field_for_type(spec.schema_annotation, options)


def _field_for_type(annotation: Any, options: dict[str, Any]) -> fields.Field[Any]:
    """Map a Python annotation onto a concrete Marshmallow field."""

    annotation, _ = unwrap_optional(annotation)

    if (scalar := _SCALARS.get(annotation)) is not None:
        return scalar(**options)

    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        # Enums that carry a scalar value round-trip by value; the rest by name.
        by_value = issubclass(annotation, (str, int))
        return fields.Enum(annotation, by_value=by_value, **options)

    origin = get_origin(annotation)

    if origin in _SEQUENCES:
        args = [arg for arg in get_args(annotation) if arg is not Ellipsis]
        inner = _field_for_type(args[0], {}) if args else fields.Raw()
        return fields.List(inner, **options)

    if origin is Literal:
        options.setdefault("validate", validate.OneOf(get_args(annotation)))
        return fields.Raw(**options)

    if origin is dict:
        return fields.Dict(**options)

    # Unknown annotation: pass the value through untouched rather than guessing.
    return fields.Raw(**options)


def _coercer(request: SchemaRequest) -> Any:
    """A ``pre_load`` hook turning null-like strings into ``None``."""

    nullable = frozenset(request.nullable_names)

    def coerce_null_strings(_: Any, data: Mapping[str, Any], **__: Any) -> dict[str, Any]:
        return {
            key: None if key in nullable and request.is_null_string(value) else value
            for key, value in data.items()
        }

    return coerce_null_strings
