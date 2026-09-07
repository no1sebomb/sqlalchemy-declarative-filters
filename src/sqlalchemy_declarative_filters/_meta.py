"""The metaclass and base class that turn a class body of methods into filters."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from ._backends import SchemaRequest, get_backend
from ._exceptions import FilterDeclarationError, UnknownFilterError
from ._joins import JoinTracker, Statement, unwrap
from ._spec import collect_specs

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ._spec import FilterSpec

__all__ = ("Filters", "FiltersMeta")

#: Names the statement offers a filter body, so they are never filter names.
_RESERVED: frozenset[str] = frozenset({"where", "having", "join", "outerjoin", "unwrap"})


class _SchemaAccessor:
    """Exposes a lazily built schema as a class attribute of a filters class.

    Lives on the metaclass, so ``MyFilters.Schema`` reaches ``__get__`` with the
    filters class itself. That is what keeps the cache per class: a subclass that adds
    a filter builds its own schema rather than inheriting its parent's.
    """

    __slots__ = ("_backend_name",)

    def __init__(self, backend_name: str | None = None) -> None:
        # None means "whatever this class's __backend__ says".
        self._backend_name = backend_name

    def __get__(self, cls: Any, owner: type | None = None) -> Any:
        if cls is None:
            return self

        return cls.build_schema(self._backend_name)


class FiltersMeta(type):
    """Metaclass giving filters classes their schemas and their ``apply``."""

    # Set on every filters class by __new__, so each gets its own.
    __schema_cache__: dict[str, type[Any]]
    __filter_specs__: tuple[FilterSpec, ...] | None

    # Declared in the Filters body, but read through the metaclass.
    __backend__: str
    __null_strings__: frozenset[str]
    __schema_name__: str

    #: The generated schema, in whichever backend ``__backend__`` names.
    Schema = _SchemaAccessor()

    #: Alias of :attr:`Schema`, for the backends that call these things models.
    Model = _SchemaAccessor()

    Dataclass = _SchemaAccessor("dataclass")
    Pydantic = _SchemaAccessor("pydantic")
    Marshmallow = _SchemaAccessor("marshmallow")

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> FiltersMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # Per-class, so subclasses never see a parent's cached schema.
        cls.__schema_cache__ = {}
        cls.__filter_specs__ = None

        return cls

    @property
    def __filters__(cls) -> tuple[FilterSpec, ...]:
        """The filters declared on this class and inherited from its bases."""

        if cls.__dict__.get("__filter_specs__") is None:
            cls.__filter_specs__ = collect_specs(cls, _RESERVED)

        return cls.__dict__["__filter_specs__"]  # type: ignore[no-any-return]

    def build_schema(cls, backend: str | None = None) -> type[Any]:
        """Return this class's schema for ``backend``, building it once.

        ``backend`` defaults to the class's ``__backend__``, which is what the base
        class you inherited from set.
        """

        name = backend or cls.__backend__
        cache = cls.__dict__["__schema_cache__"]

        if (schema := cache.get(name)) is None:
            # Not exists yet, need to build
            implementation = get_backend(name)

            try:
                schema = cache[name] = implementation.build(cls._schema_request())
            except TypeError as exc:
                raise FilterDeclarationError(
                    f"The {name!r} backend could not build a schema for "
                    f"{cls.__name__}: {exc}. @options keywords go to the backend's "
                    f"own field constructor, so import options from the same "
                    f"namespace as the Filters class you inherit from."
                ) from exc

        return schema  # type: ignore[no-any-return]

    def apply(cls, statement: Any, values: Any = None) -> Any:
        """Apply the filters in ``values`` to ``statement`` and return the result.

        ``values`` may be a mapping, an instance of this class's generated
        schemas, or ``None``. Filters whose value is ``None`` are skipped; filters
        that declare a default are applied with it when ``values`` omits them.

        Every applied filter shares one record of what has been joined, seeded from
        ``statement``, so ``self.join(...)`` is idempotent: a target is joined at most
        once however many filters ask for it, and never if the caller joined it first.
        """

        data = _to_mapping(cls, values)
        specs = cls.__filters__

        if unknown := set(data) - {spec.name for spec in specs}:
            # Got unknown filters
            names = ", ".join(sorted(unknown))
            raise UnknownFilterError(f"{cls.__name__} has no filter(s) named {names}.")

        tracker = JoinTracker(statement)
        current = Statement(statement, tracker)

        for spec, value in _active(specs, data):
            # The filter method is unbound: `self` is the statement being built.
            result = spec.func(current, value)

            if result is None:
                raise TypeError(
                    f"Filter {cls.__name__}.{spec.name} returned None. A filter must "
                    f"return the narrowed statement, as in `return self.where(...)`."
                )

            # A filter that unwrapped along the way still gets deduplicated joins.
            current = result if isinstance(result, Statement) else Statement(result, tracker)

        return unwrap(current)

    def _schema_request(cls) -> SchemaRequest:
        """Package this class up for a backend to render."""

        return SchemaRequest(
            name=getattr(cls, "__schema_name__", None) or f"{cls.__name__}Schema",
            doc=cls.__doc__,
            module=cls.__module__,
            specs=cls.__filters__,
            null_strings=frozenset(cls.__null_strings__),
        )


def _active(
    specs: tuple[FilterSpec, ...],
    data: Mapping[str, Any],
) -> Iterator[tuple[FilterSpec, Any]]:
    """Yield ``(spec, value)`` for the filters that should run, in declaration order.

    Declaration order rather than the order of ``data`` so that the same filters
    always compile to the same SQL, which keeps statement caching effective.
    """

    for spec in specs:
        if spec.name in data:
            value = data[spec.name]
        elif spec.has_default:
            # A declared default holds whether the caller mentioned the filter.
            value = spec.default
        else:
            continue

        if value is not None:
            yield spec, value


def _to_mapping(cls: type, values: Any) -> Mapping[str, Any]:
    """Normalize whatever ``apply`` was handed into a plain mapping."""

    if values is None:
        return {}

    if isinstance(values, dict):
        return values

    if dataclasses.is_dataclass(values) and not isinstance(values, type):
        return {field.name: getattr(values, field.name) for field in dataclasses.fields(values)}

    if (model_dump := getattr(values, "model_dump", None)) and callable(model_dump):
        # Pydantic. Defaults are kept; `_active` decides what actually applies.
        return dict(model_dump())

    try:
        # Any other case => try plain converting to dict
        return dict(values)
    except (TypeError, ValueError):
        raise TypeError(
            f"{cls.__name__}.apply() takes a mapping, one of this class's generated "
            f"schemas, or None, got {type(values).__name__}."
        ) from None


class Filters(metaclass=FiltersMeta):
    """Base class for a set of filters.

    Every public method in the body is a filter. It takes the statement being built as
    ``self`` and the filter's value as its only other parameter, and returns the
    narrowed statement::

        class BookFilters(Filters):
            def title(self, value: str):
                \"""Books whose title contains this.\"""
                return self.where(Book.title.ilike(f"%{value}%"))

    The parameter's annotation becomes the schema field's type, its default becomes
    the field's default, and the docstring becomes the field's description.
    """

    #: Which backend :attr:`Schema` uses. Set by the base class you inherit from.
    __backend__ = "dataclass"

    #: Strings a query parameter may use to mean ``null`` on a ``@skip_null`` filter.
    __null_strings__ = frozenset({"", "null", "none"})
