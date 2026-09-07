"""The Pydantic backend: a ``BaseModel`` subclass, validation included.

``@options`` keywords go straight to :func:`pydantic.Field`, so constraints such as
``min_length`` and ``ge`` work as they would on a handwritten model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, create_model, field_validator

from .base import SchemaBackend

if TYPE_CHECKING:
    from .base import SchemaRequest

__all__ = ("PydanticBackend",)


class PydanticBackend(SchemaBackend):
    """Renders filters as a Pydantic model."""

    name = "pydantic"
    extra = "pydantic"

    def build(self, request: SchemaRequest) -> type[BaseModel]:
        fields: dict[str, Any] = {}

        for spec in request.specs:
            options = dict(spec.options)
            options.setdefault("description", spec.doc)
            fields[spec.name] = (
                spec.schema_annotation,
                Field(default=spec.schema_default, **options),
            )

        validators: dict[str, Any] = {}

        if names := request.nullable_names:
            # `mode="before"` so the empty string is caught ahead of type coercion.
            validators["_coerce_null_strings"] = field_validator(*names, mode="before")(
                _coercer(request)
            )

        return create_model(
            request.name,
            __doc__=request.doc,
            __module__=request.module,
            __validators__=validators,
            **fields,
        )


def _coercer(request: SchemaRequest) -> Any:
    """A ``mode="before"`` validator turning null-like strings into ``None``."""

    def coerce_null_strings(_, value: Any) -> Any:
        return None if request.is_null_string(value) else value

    return classmethod(coerce_null_strings)
