"""Params: filters and sorting behind one schema, for frameworks that take one model.

FastAPI reads a single model per endpoint from the query string. A :class:`Params` class
names the filters and sorting classes a list endpoint uses, and renders all of their
fields as one schema::

    class BookParams(Params[Book]):
        filters = BookFilters
        sorting = BookSorting

Its ``apply`` runs every part over the statement. Each part can also be applied on its
own to an instance of that schema, and reads only its own fields from it -- which is
what a count query, filtered but not sorted, needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, cast

from sqlalchemy import select

from ._backends import SchemaRequest
from ._exceptions import FilterDeclarationError, UnknownFilterError
from ._meta import FiltersMeta, ModelT, SchemaMeta, to_mapping
from ._sorting import SortingMeta

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ._spec import FilterSpec

__all__ = ("PARAMS_ATTR", "Params", "ParamsMeta")

#: Set on every schema a params class builds, naming that class, so that a part handed
#: an instance of it can tell which of the fields are its own.
PARAMS_ATTR = "__filters_params__"


@dataclass(frozen=True)
class _Part:
    """One filters or sorting class of a params class, and the fields it reads."""

    name: str
    cls: Any
    fields: tuple[FilterSpec, ...]

    @property
    def field_names(self) -> frozenset[str]:
        return frozenset(field.name for field in self.fields)


class ParamsMeta(SchemaMeta):
    """Metaclass giving params classes their combined schema and their ``apply``."""

    # Set on every params class by __new__, so each gets its own.
    __params_parts__: tuple[_Part, ...] | None

    _base_name = "Params"

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> ParamsMeta:
        cls = cast("ParamsMeta", super().__new__(mcs, name, bases, namespace, **kwargs))
        cls.__params_parts__ = None

        return cls

    @property
    def __parts__(cls) -> dict[str, Any]:
        """The filters and sorting classes this class combines, by attribute name."""

        return {part.name: part.cls for part in cls._parts()}

    def apply(cls, statement: Any, values: Any = None) -> Any:
        """Apply every part to ``statement``: the filters, then the sorting.

        ``values`` may be a mapping, an instance of this class's generated schemas, or
        ``None``. Each part is handed the values of its own fields, so its defaults
        apply exactly as they would if it were applied alone.
        """

        data = to_mapping(cls, values)
        parts = cls._parts()

        if unknown := set(data) - {name for part in parts for name in part.field_names}:
            names = ", ".join(sorted(unknown))
            raise UnknownFilterError(f"{cls.__name__} has no parameter(s) named {names}.")

        # Filters first, so that a sort joining a table a filter joined finds it there.
        for part in sorted(parts, key=lambda part: isinstance(part.cls, SortingMeta)):
            own = part.field_names
            statement = part.cls.apply(
                statement, {name: value for name, value in data.items() if name in own}
            )

        return statement

    def statement(cls, values: Any = None) -> Any:
        """Select this class's model with every part applied.

        ``BookParams.statement(values)`` is ``BookParams.apply(select(Book), values)``.
        Needs the model: parameterize the class as ``Params[Book]``, or set
        ``__model__``.
        """

        return cls.apply(select(cls._model("statement")), values)

    def build_schema(cls, backend: str | None = None) -> type[Any]:
        schema = super().build_schema(backend)
        # Read by to_mapping, when a part is applied to an instance of this schema.
        setattr(schema, PARAMS_ATTR, cls)

        return schema

    def _values_for(cls, part: Any, data: Mapping[str, Any]) -> Mapping[str, Any]:
        """The values in ``data`` that belong to ``part``, one of this class's parts."""

        for candidate in cls._parts():
            if candidate.cls is part:
                return {
                    name: value for name, value in data.items() if name in candidate.field_names
                }

        names = ", ".join(candidate.cls.__name__ for candidate in cls._parts())
        raise TypeError(
            f"{part.__name__}.apply() was handed a {cls.__name__} schema, which combines "
            f"{names}; {part.__name__} is not one of them."
        )

    def _parts(cls) -> tuple[_Part, ...]:
        """Collect and check the parts, once."""

        if (parts := cls.__dict__.get("__params_parts__")) is not None:
            return parts  # type: ignore[no-any-return]

        declared: dict[str, Any] = {}

        # Everything the params class itself answers to; a part of that name would shadow it.
        provided = frozenset(name for name in dir(type(cls)) if not name.startswith("_"))

        for klass in reversed(cls.__mro__):
            for name, value in vars(klass).items():
                if name.startswith("_"):
                    continue

                if name in provided:
                    raise FilterDeclarationError(
                        f"{klass.__qualname__}.{name} cannot be a part: {name!r} is one of "
                        f"the things the params class itself provides "
                        f"({', '.join(sorted(provided))}), and a part of that name would "
                        f"shadow it. Rename it."
                    )

                if not isinstance(value, (FiltersMeta, SortingMeta)):
                    raise FilterDeclarationError(
                        f"{klass.__qualname__}.{name} is {value!r}, which is not a Filters "
                        f"or Sorting class. Every public attribute of a Params class is one "
                        f"of its parts; prefix anything else with `_`."
                    )

                declared[name] = value

        parts = tuple(_Part(name, part, _fields(part)) for name, part in declared.items())

        _check(cls, parts)
        cls.__params_parts__ = parts

        return parts

    def _schema_request(cls) -> SchemaRequest:
        """Package the parts' fields up for a backend to render, as one schema."""

        parts = cls._parts()

        return SchemaRequest(
            name=getattr(cls, "__schema_name__", None) or f"{cls.__name__}Schema",
            doc=cls.__doc__,
            module=cls.__module__,
            specs=tuple(field for part in parts for field in part.fields),
            null_strings=frozenset().union(
                *(part.cls.__null_strings__ for part in parts if isinstance(part.cls, FiltersMeta))
            ),
        )


def _fields(part: Any) -> tuple[FilterSpec, ...]:
    """The schema fields a filters or sorting class contributes."""

    if isinstance(part, FiltersMeta):
        return part.__filters__

    return cast("SortingMeta", part)._config().fields()


def _check(cls: ParamsMeta, parts: tuple[_Part, ...]) -> None:
    """Refuse combinations that cannot be one schema, or one statement."""

    if len(sortings := [part for part in parts if isinstance(part.cls, SortingMeta)]) > 1:
        names = ", ".join(part.name for part in sortings)
        raise FilterDeclarationError(
            f"{cls.__name__} has more than one sorting part ({names}). A statement is "
            f"ordered one way; combine the sorts into one Sorting class."
        )

    owners: dict[str, _Part] = {}

    for part in parts:
        for name in part.field_names:
            if (other := owners.get(name)) is not None:
                raise FilterDeclarationError(
                    f"{cls.__name__} cannot combine {other.cls.__name__} and "
                    f"{part.cls.__name__}: both read a field named {name!r}. Rename one "
                    f"of them -- for a sorting class, through __sort_field__ or "
                    f"__order_field__."
                )

            owners[name] = part

    if (model := cls.__model__) is None:
        return

    for part in parts:
        if part.cls.__model__ is not None and part.cls.__model__ is not model:
            raise FilterDeclarationError(
                f"{cls.__name__} is over {model.__name__}, but its part {part.name!r}, "
                f"{part.cls.__name__}, is over {part.cls.__model__.__name__}."
            )


class Params(Generic[ModelT], metaclass=ParamsMeta):
    """Base class combining filters and sorting classes behind one schema.

    Every public attribute is a part: a ``Filters`` class, or one ``Sorting`` class::

        class BookParams(Params[Book]):
            \"""Parameters for listing the book catalogue.\"""

            filters = BookFilters
            sorting = BookSorting

    ``BookParams.Schema`` has every part's fields, in declaration order, and its
    docstring. ``BookParams.apply`` runs the filters and then the sorting. A subclass
    can add parts, or replace one under the same name -- with a subclass of it, as a
    type checker will insist.
    """

    #: Which backend :attr:`Schema` uses. Set by the base class you inherit from.
    __backend__ = "dataclass"
