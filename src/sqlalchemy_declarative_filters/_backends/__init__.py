"""Schema backend registry.

Backends are imported the first time they are asked for, so importing this package
never pulls in Pydantic or Marshmallow.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

from .._exceptions import BackendNotAvailableError
from .base import SchemaBackend, SchemaRequest

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ("SchemaBackend", "SchemaRequest", "backend_names", "get_backend")

#: name -> (module, class, extra to install)
_BACKENDS: dict[str, tuple[str, str, str | None]] = {
    "dataclass": (".dataclass", "DataclassBackend", None),
    "pydantic": (".pydantic", "PydanticBackend", "pydantic"),
    "marshmallow": (".marshmallow", "MarshmallowBackend", "marshmallow"),
}

_LOADED: dict[str, SchemaBackend] = {}


def backend_names() -> Iterator[str]:
    """The names :func:`get_backend` accepts."""

    return iter(_BACKENDS)


def get_backend(name: str) -> SchemaBackend:
    """Return the backend called ``name``, importing it on first use."""

    if (backend := _LOADED.get(name)) is not None:
        return backend

    try:
        module_name, class_name, extra = _BACKENDS[name]
    except KeyError:
        known = ", ".join(sorted(_BACKENDS))
        raise ValueError(f"Unknown schema backend {name!r}; expected one of {known}.") from None

    try:
        module = import_module(module_name, __name__)
    except ImportError as exc:
        raise BackendNotAvailableError(
            f"The {name!r} schema backend needs a dependency that is not installed: "
            f"{exc}. Install it with "
            f"`pip install sqlalchemy-declarative-filters[{extra}]`."
        ) from exc

    backend = _LOADED[name] = cast("SchemaBackend", getattr(module, class_name)())

    return backend
