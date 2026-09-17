"""Sorting: a class body of methods, each one way the caller may order the results.

A sort takes no value. The caller picks one by name and, optionally, a direction; the
method writes the ascending order, and the direction is applied to it on the way
through ``self.order_by(...)``. How the choice arrives -- ``?sort=title&order=desc``,
``?sort_by=title&asc=0``, ``?sort=-title`` -- is a property of the class, set by
``__sort_field__``, ``__order_field__`` and ``__order_style__``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Literal, cast

from sqlalchemy import asc, desc, nulls_first, nulls_last, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import UnaryExpression

from ._backends import SchemaRequest
from ._exceptions import FilterDeclarationError, InvalidOrderError, UnknownSortError
from ._joins import JoinTracker, Statement, unwrap
from ._meta import ModelT, SchemaMeta, to_mapping
from ._spec import FilterSpec, SortSpec, collect_specs

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ("PRIMARY_KEY", "OrderStyle", "SortStatement", "Sorting", "SortingMeta", "reverse")


class OrderStyle(str, enum.Enum):
    """How the caller spells the direction of a sort.

    Set on a sorting class as ``__order_style__ = OrderStyle.PREFIX``. A ``str`` enum,
    so the plain value -- ``"prefix"`` -- is accepted at runtime too.
    """

    #: ``?sort=title&order=desc``: ``asc`` or ``desc`` in the order field.
    CODE = "code"

    #: ``?sort=title&asc=0``: a boolean saying "ascending".
    ASC_FLAG = "asc_flag"

    #: ``?sort=title&desc=1``: a boolean saying "descending".
    DESC_FLAG = "desc_flag"

    #: ``?sort=-title``: a ``-`` on the sort name, and no order field at all.
    PREFIX = "prefix"


#: The order field's name when ``__order_field__`` does not give one.
_ORDER_FIELDS: dict[OrderStyle, str | None] = {
    OrderStyle.CODE: "order",
    OrderStyle.ASC_FLAG: "asc",
    OrderStyle.DESC_FLAG: "desc",
    OrderStyle.PREFIX: None,
}

#: Names a sort body calls on the statement, so they are never sort names.
_RESERVED: frozenset[str] = frozenset(
    {"where", "having", "join", "outerjoin", "unwrap", "order_by"}
)

#: The values of the ``"code"`` style, and what each says about descending.
_CODES: dict[str, bool] = {"asc": False, "desc": True}

_NULLS = (operators.nulls_first_op, operators.nulls_last_op)


class _PrimaryKey:
    """The default ``__tiebreaker__``: the model's primary key, when the model is known.

    Exported as ``PRIMARY_KEY``, so that a subclass of a class that set its own
    tiebreaker -- or ``None`` -- can ask for the default back.
    """

    def __repr__(self) -> str:
        return "PRIMARY_KEY"


PRIMARY_KEY: Any = _PrimaryKey()


def reverse(clause: Any) -> Any:
    """Turn one ``ORDER BY`` key round, leaving a ``NULLS FIRST/LAST`` where it was.

    Nulls stay put because that is what a caller flipping the direction expects: the
    rows without a value are still the least interesting ones, whichever way the rest
    are read.
    """

    if isinstance(clause, UnaryExpression):
        if clause.modifier in _NULLS:
            wrap = nulls_first if clause.modifier is operators.nulls_first_op else nulls_last
            return wrap(reverse(clause.element))

        if clause.modifier is operators.desc_op:
            return asc(clause.element)

        if clause.modifier is operators.asc_op:
            return desc(clause.element)

    return desc(clause)


class SortStatement(Statement):
    """The statement being sorted, as a sort body sees it.

    A :class:`~._joins.Statement` -- joins are deduplicated as they are in a filter --
    whose ``order_by`` also applies the direction the caller asked for. A sort body
    therefore always writes its ascending order, and ``desc`` reverses every key it
    gave: ``asc`` becomes ``desc`` and ``desc`` becomes ``asc``.
    """

    __slots__ = ("_descending",)

    def __init__(self, statement: Any, tracker: JoinTracker, descending: bool) -> None:
        super().__init__(statement, tracker)
        self._descending = descending

    def order_by(self, *clauses: Any) -> Any:
        """``Select.order_by``, with each key turned round when sorting descending."""

        if self._descending:
            clauses = tuple(clause if clause is None else reverse(clause) for clause in clauses)

        return self._rewrap(self._statement.order_by(*clauses))

    def _rewrap(self, result: Any) -> Any:
        if isinstance(result, type(self._statement)):
            return SortStatement(result, self._tracker, self._descending)

        return result


@dataclass(frozen=True)
class _SortConfig:
    """A sorting class's declarations, resolved and checked once."""

    specs: dict[str, SortSpec]
    sort_field: str
    order_field: str | None
    style: OrderStyle
    default: str | None

    def choose(self, owner: str, data: Mapping[str, Any]) -> tuple[SortSpec, bool] | None:
        """Pick the sort and direction ``data`` asks for, or ``None`` for no sorting."""

        known = (
            [self.sort_field] if self.order_field is None else [self.sort_field, self.order_field]
        )

        if unknown := set(data) - set(known):
            names = ", ".join(sorted(unknown))
            expected = " and ".join(repr(name) for name in known)
            raise UnknownSortError(f"{owner} has no field(s) named {names}; it reads {expected}.")

        name = data.get(self.sort_field)
        descending: bool | None = None

        if self.style is OrderStyle.PREFIX:
            if isinstance(name, str) and name.startswith("-"):
                name, descending = name[1:], True
            elif name is not None:
                descending = False
        elif self.order_field is not None:
            descending = self._direction(owner, data.get(self.order_field))

        if name is None:
            # Nothing chosen: the declared default, in its own direction.
            if self.default is None:
                return None

            name = self.default

        if not isinstance(name, str) or (spec := self.specs.get(name)) is None:
            choices = ", ".join(self.specs)
            raise UnknownSortError(
                f"{owner} has no sort named {name!r}; expected one of {choices}."
            )

        return spec, spec.descending if descending is None else descending

    def _direction(self, owner: str, value: Any) -> bool | None:
        """Read the order field's value as "descending?", ``None`` when not given."""

        if value is None:
            return None

        if self.style is OrderStyle.CODE:
            if isinstance(value, str) and value in _CODES:
                return _CODES[value]

            raise InvalidOrderError(
                f"{owner}.{self.order_field} must be 'asc' or 'desc', got {value!r}."
            )

        if not isinstance(value, bool):
            raise InvalidOrderError(
                f"{owner}.{self.order_field} must be a bool, got {value!r}. Validate the "
                f"input with the Pydantic or Marshmallow schema to accept strings "
                f"such as '0' and 'true'."
            )

        return value if self.style is OrderStyle.DESC_FLAG else not value

    def fields(self) -> tuple[FilterSpec, ...]:
        """The schema fields, described the way the backends already render filters.

        None at all when the class declares no sorts: there is nothing for the sort
        field to choose from, so a class still being written -- or a base others add
        their sorts to -- contributes no fields rather than an empty ``Literal``.
        """

        if not self.specs:
            return ()

        fields = [self._sort_field()]

        if self.order_field is not None:
            fields.append(self._order_field())

        return tuple(fields)

    def _sort_field(self) -> FilterSpec:
        if self.style is OrderStyle.PREFIX:
            choices = tuple(choice for name in self.specs for choice in (name, f"-{name}"))
            default = self.default

            if default is not None and self.specs[default].descending:
                default = f"-{default}"

            intro = "How to order the results. Prefix it with `-` to sort descending."
        else:
            choices = tuple(self.specs)
            default = self.default
            intro = "How to order the results."

        lines = [intro, ""]

        for spec in self.specs.values():
            line = f"- `{spec.name}`"

            if spec.summary:
                line = f"{line}: {spec.summary}"

            if spec.descending and self.style is not OrderStyle.PREFIX:
                line = f"{line} Descending unless stated otherwise."

            if spec.deprecated:
                line = f"{line} Deprecated: {spec.deprecation_message}"

            lines.append(line)

        return FilterSpec(
            name=self.sort_field,
            func=_schema_only,
            annotation=Literal[choices],
            default=default,
            has_default=default is not None,
            doc="\n".join(lines),
        )

    def _order_field(self) -> FilterSpec:
        annotation: Any
        omitted = "Omitted, each sort uses its own default direction."

        if self.style is OrderStyle.CODE:
            annotation, doc = Literal["asc", "desc"], f"`asc` or `desc`. {omitted}"
        elif self.style is OrderStyle.ASC_FLAG:
            annotation, doc = bool, f"Whether to sort ascending. {omitted}"
        else:
            annotation, doc = bool, f"Whether to sort descending. {omitted}"

        return FilterSpec(
            name=self.order_field,  # type: ignore[arg-type]
            func=_schema_only,
            annotation=annotation,
            doc=doc,
        )


def _schema_only(*_: Any) -> Any:  # pragma: no cover - never applied
    """Stands in for a filter method on the synthetic specs that only describe fields."""

    raise NotImplementedError


class SortingMeta(SchemaMeta):
    """Metaclass giving sorting classes their schemas and their ``apply``."""

    # Set on every sorting class by __new__, so each gets its own.
    __sort_config__: _SortConfig | None

    # Declared in the Sorting body, but read through the metaclass.
    __sort_field__: str
    __order_field__: str | None
    __order_style__: OrderStyle
    __default_sort__: str | None
    __tiebreaker__: Any

    _base_name = "Sorting"

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> SortingMeta:
        cls = cast("SortingMeta", super().__new__(mcs, name, bases, namespace, **kwargs))
        cls.__sort_config__ = None

        return cls

    @property
    def __sorts__(cls) -> tuple[SortSpec, ...]:
        """The sorts declared on this class and inherited from its bases."""

        return tuple(cls._config().specs.values())

    def apply(cls, statement: Any, values: Any = None) -> Any:
        """Order ``statement`` the way ``values`` asks, and return the result.

        ``values`` may be a mapping, an instance of this class's generated schemas, or
        ``None``; with nothing chosen, ``__default_sort__`` applies, and with no
        default either the statement comes back unchanged.

        The chosen sort goes first. Any ordering ``statement`` already had is kept
        after it, as a tie-breaker, followed by ``__tiebreaker__`` -- the model's
        primary key unless the class says otherwise -- so that pages never overlap.
        """

        chosen = cls._config().choose(cls.__name__, to_mapping(cls, values))

        if chosen is None:
            return statement

        spec, descending = chosen

        if not hasattr(statement, "order_by"):
            raise TypeError(
                f"{cls.__name__}.apply() needs a statement that can be ordered, got "
                f"{type(statement).__name__}."
            )

        existing = tuple(getattr(statement, "_order_by_clauses", ()))
        base = statement.order_by(None) if existing else statement

        result = spec.func(SortStatement(base, JoinTracker(base), descending))

        if result is None:
            raise TypeError(
                f"Sort {cls.__name__}.{spec.name} returned None. A sort must return "
                f"the ordered statement, as in `return self.order_by(...)`."
            )

        result = unwrap(result)

        if existing:
            result = result.order_by(*existing)

        if keys := [key for key in cls._tiebreaker() if not _orders_by(result, key)]:
            result = result.order_by(*(reverse(key) if descending else key for key in keys))

        return result

    def statement(cls, values: Any = None) -> Any:
        """Select this class's model, ordered the way ``values`` asks.

        ``BookSorting.statement(values)`` is ``BookSorting.apply(select(Book), values)``.
        Needs the model: parameterize the class as ``Sorting[Book]``, or set
        ``__model__``.
        """

        return cls.apply(select(cls._model("statement")), values)

    def _config(cls) -> _SortConfig:
        """Resolve and check the class's declarations, once."""

        if (config := cls.__dict__.get("__sort_config__")) is not None:
            return config  # type: ignore[no-any-return]

        specs = collect_specs(cls, _RESERVED, SortSpec.from_function, kind="sort")
        try:
            style = OrderStyle(cls.__order_style__)
        except ValueError:
            styles = ", ".join(f"OrderStyle.{member.name}" for member in OrderStyle)
            raise FilterDeclarationError(
                f"{cls.__name__}.__order_style__ is {cls.__order_style__!r}; expected one "
                f"of {styles}."
            ) from None

        order_field = (
            None if style is OrderStyle.PREFIX else cls.__order_field__ or _ORDER_FIELDS[style]
        )

        if order_field == cls.__sort_field__:
            raise FilterDeclarationError(
                f"{cls.__name__} reads the sort and the order from the same field, "
                f"{order_field!r}. Give __sort_field__ and __order_field__ different names."
            )

        if (default := cls.__default_sort__) is not None and default not in {
            spec.name for spec in specs
        }:
            raise FilterDeclarationError(
                f"{cls.__name__}.__default_sort__ is {default!r}, which is not one of its "
                f"sorts. Name the sort method; @descending on it sets the direction."
            )

        config = cls.__sort_config__ = _SortConfig(
            specs={spec.name: spec for spec in specs},
            sort_field=cls.__sort_field__,
            order_field=order_field,
            style=style,
            default=default,
        )

        return config

    def _tiebreaker(cls) -> tuple[Any, ...]:
        """The keys appended after the chosen sort, so equal rows keep a stable order."""

        value = cls.__tiebreaker__

        if value is None:
            return ()

        if value is PRIMARY_KEY:
            mapper = sa_inspect(cls.__model__, raiseerr=False) if cls.__model__ else None
            return tuple(getattr(mapper, "primary_key", ()))

        return tuple(value) if isinstance(value, (tuple, list)) else (value,)

    def _schema_request(cls) -> SchemaRequest:
        """Package this class up for a backend to render."""

        config = cls._config()

        return SchemaRequest(
            name=getattr(cls, "__schema_name__", None) or f"{cls.__name__}Schema",
            doc=cls.__doc__,
            module=cls.__module__,
            specs=config.fields(),
            null_strings=frozenset(),
        )


def _orders_by(statement: Any, key: Any) -> bool:
    """Whether ``statement`` already orders by ``key``, in either direction."""

    for clause in getattr(statement, "_order_by_clauses", ()):
        while isinstance(clause, UnaryExpression) and clause.modifier is not None:
            clause = clause.element

        if hasattr(clause, "compare") and clause.compare(key):
            return True

    return False


class Sorting(Generic[ModelT], metaclass=SortingMeta):
    """Base class for a set of sorts.

    Every public method in the body is a sort. It takes the statement being built as
    ``self``, and nothing else, and returns it ordered -- always in ascending order;
    the caller's direction is applied to ``self.order_by(...)`` for you::

        class BookSorting(Sorting[Book]):
            __default_sort__ = "title"

            def title(self):
                \"""By title.\"""
                return self.order_by(Book.title)

            @descending
            def rating(self):
                \"""By average review score.\"""
                return self.order_by(average_rating.nulls_last())

    The docstrings describe the choices of the generated schema's sort field.
    """

    #: Which backend :attr:`Schema` uses. Set by the base class you inherit from.
    __backend__ = "dataclass"

    #: The name of the field that picks the sort.
    __sort_field__ = "sort"

    #: The name of the field that picks the direction. ``None`` names it after the
    #: style: ``order``, ``asc`` or ``desc``. The ``"prefix"`` style has none.
    __order_field__: str | None = None

    #: How the direction is spelled: :class:`OrderStyle` ``CODE`` (``order=desc``),
    #: ``ASC_FLAG`` (``asc=false``), ``DESC_FLAG`` (``desc=true``) or ``PREFIX``
    #: (``sort=-title``).
    __order_style__ = OrderStyle.CODE

    #: The sort applied when the caller chooses none; ``None`` leaves the order alone.
    __default_sort__: str | None = None

    #: Keys appended after every sort so that equal rows keep a stable order: the
    #: model's primary key by default, a column or a tuple of them, or ``None``.
    __tiebreaker__: Any = PRIMARY_KEY
