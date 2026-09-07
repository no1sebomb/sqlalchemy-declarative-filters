"""The contract every schema backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .._spec import FilterSpec

__all__ = ("SchemaBackend", "SchemaRequest")


@dataclass(frozen=True)
class SchemaRequest:
    """Everything a backend needs to render one filter class as a schema."""

    name: str
    doc: str | None
    module: str
    specs: tuple[FilterSpec, ...]
    null_strings: frozenset[str]

    def is_null_string(self, value: Any) -> bool:
        """Whether ``value`` is one of the strings that stand in for ``null``."""

        return isinstance(value, str) and value.strip().lower() in self.null_strings

    def coerce(self, value: Any) -> Any:
        """Map a null-like string to ``None`` for filters that opted into it."""

        return None if self.is_null_string(value) else value

    @property
    def nullable_names(self) -> tuple[str, ...]:
        """Names of the filters whose null-like strings should become ``None``."""

        return tuple(spec.name for spec in self.specs if spec.skip_null)


class SchemaBackend(ABC):
    """Renders :class:`~.._spec.FilterSpec` objects into a schema class."""

    #: The name this backend is selected by.
    name: ClassVar[str]

    #: The extra to install to get it, or ``None`` when it needs no dependency.
    extra: ClassVar[str | None] = None

    @abstractmethod
    def build(self, request: SchemaRequest) -> type[Any]:
        """Build and return the schema class for ``request``."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r}>"
