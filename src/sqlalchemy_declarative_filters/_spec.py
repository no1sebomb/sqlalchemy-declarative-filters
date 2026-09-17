"""Introspection of filter and sorting classes into plain, backend-agnostic descriptions.

Nothing in this module knows about dataclasses, Pydantic or Marshmallow. It turns
a class body full of decorated methods into :class:`FilterSpec` and :class:`SortSpec`
objects, which the schema backends and ``apply`` then work from.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, Any, TypeVar, Union, get_type_hints

from ._exceptions import FilterDeclarationError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

__all__ = ("Deprecation", "FilterSpec", "SortSpec", "collect_specs", "unwrap_optional")

#: Attribute names the decorators write onto filter methods.
OPTIONS_ATTR = "__filter_options__"
SKIP_NULL_ATTR = "__filter_skip_null__"
DEPRECATION_ATTR = "__filter_deprecation__"
DESCENDING_ATTR = "__sort_descending__"


@dataclass(frozen=True)
class Deprecation:
    """What ``@deprecated`` recorded about a filter on its way out."""

    reason: str | None = None
    alternative: str | None = None


@dataclass(frozen=True)
class FilterSpec:
    """Everything the schema backends and :func:`apply` need about one filter."""

    name: str
    func: Callable[..., Any]
    annotation: Any
    default: Any = None
    has_default: bool = False
    skip_null: bool = False
    doc: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    deprecation: Deprecation | None = None

    @property
    def deprecated(self) -> bool:
        """Whether this filter is on its way out."""

        return self.deprecation is not None

    @property
    def deprecation_message(self) -> str | None:
        """The sentence to show a caller who still uses this filter."""

        return _deprecation_message("filter", self.name, self.deprecation)

    @property
    def schema_description(self) -> str | None:
        """The description the generated schema field should carry.

        The docstring, with the deprecation note appended when there is one: OpenAPI
        has a ``deprecated`` flag but nowhere to say why, so the why goes here.
        """

        if (message := self.deprecation_message) is None:
            return self.doc

        return f"{self.doc}\n\nDeprecated: {message}" if self.doc else f"Deprecated: {message}"

    @property
    def optional(self) -> bool:
        """Whether ``None`` is an accepted value for this filter.

        A filter with no declared default is optional because omitting it is how you
        say "do not filter on this". A filter *with* a default is only optional when
        it opts in via ``@skip_null``, which is what makes the default switchable off.
        """

        return not self.has_default or self.skip_null

    @property
    def schema_annotation(self) -> Any:
        """The annotation the generated schema field should carry.

        Built with the ``|`` operator rather than ``Optional[...]`` because the
        annotation is a value here, not a type expression. Both spell the same type.
        """

        return (self.annotation | None) if self.optional else self.annotation

    @property
    def schema_default(self) -> Any:
        """The default the generated schema field should carry."""

        return self.default if self.has_default else None

    @classmethod
    def from_function(cls, name: str, func: Callable[..., Any]) -> FilterSpec:
        """Build a spec from a decorated filter method.

        The method is never bound: :func:`apply` calls it with the SQLAlchemy
        statement in the ``self`` position, so its first parameter is the statement
        and its second is the filter value.
        """

        params = list(inspect.signature(func).parameters.values())[1:]  # drop `self`

        if len(params) != 1:
            raise FilterDeclarationError(
                f"Filter {func.__qualname__} must take exactly one parameter besides "
                f"the statement (self), got {len(params)}."
            )

        if getattr(func, DESCENDING_ATTR, False):
            raise FilterDeclarationError(
                f"Filter {func.__qualname__} cannot be @descending: a filter has no "
                f"direction. @descending belongs on a sort, in a Sorting class."
            )

        param = params[0]
        annotation = _resolve_annotation(func, param)
        default = param.default
        has_default = default is not inspect.Parameter.empty

        return cls(
            name=name,
            func=func,
            annotation=annotation,
            default=default if has_default else None,
            has_default=has_default,
            skip_null=getattr(func, SKIP_NULL_ATTR, False),
            doc=inspect.cleandoc(func.__doc__) if func.__doc__ else None,
            options=dict(getattr(func, OPTIONS_ATTR, {})),
            deprecation=getattr(func, DEPRECATION_ATTR, None),
        )


@dataclass(frozen=True)
class SortSpec:
    """Everything the schema and :func:`apply` need about one sort."""

    name: str
    func: Callable[..., Any]
    descending: bool = False
    doc: str | None = None
    deprecation: Deprecation | None = None

    @property
    def deprecated(self) -> bool:
        """Whether this sort is on its way out."""

        return self.deprecation is not None

    @property
    def deprecation_message(self) -> str | None:
        """The sentence to show a caller who still uses this sort."""

        return _deprecation_message("sort", self.name, self.deprecation)

    @property
    def summary(self) -> str | None:
        """The docstring's first paragraph, on one line, for a list of choices."""

        if not self.doc:
            return None

        return " ".join(self.doc.split("\n\n", 1)[0].split())

    @classmethod
    def from_function(cls, name: str, func: Callable[..., Any]) -> SortSpec:
        """Build a spec from a decorated sort method.

        Like a filter, the method is never bound: ``apply`` calls it with the statement
        in the ``self`` position. Unlike a filter, it takes nothing else -- choosing
        the sort is the whole of the caller's input.
        """

        params = list(inspect.signature(func).parameters.values())[1:]  # drop `self`

        if params:
            raise FilterDeclarationError(
                f"Sort {func.__qualname__} must take no parameters besides the "
                f"statement (self), got {len(params)}. A sort is chosen by name; the "
                f"direction is applied to its order_by() for you."
            )

        for attribute, decorator in ((OPTIONS_ATTR, "@options"), (SKIP_NULL_ATTR, "@skip_null")):
            if hasattr(func, attribute):
                raise FilterDeclarationError(
                    f"Sort {func.__qualname__} cannot use {decorator}: a sort has no "
                    f"schema field of its own. It is one of the choices of the sort "
                    f"field."
                )

        return cls(
            name=name,
            func=func,
            descending=getattr(func, DESCENDING_ATTR, False),
            doc=inspect.cleandoc(func.__doc__) if func.__doc__ else None,
            deprecation=getattr(func, DEPRECATION_ATTR, None),
        )


def _deprecation_message(kind: str, name: str, deprecation: Deprecation | None) -> str | None:
    """The sentence to show a caller who still uses a deprecated filter or sort."""

    if deprecation is None:
        return None

    message = deprecation.reason or f"The {name!r} {kind} is deprecated."

    if deprecation.alternative:
        message = f"{message} Use {deprecation.alternative!r} instead."

    return message


def _resolve_annotation(func: Callable[..., Any], param: inspect.Parameter) -> Any:
    """Resolve a parameter annotation to a real type object.

    Goes through :func:`typing.get_type_hints` so that string annotations -- from
    ``from __future__ import annotations`` or an explicit quoted forward reference --
    become the types they name.
    """

    if param.annotation is inspect.Parameter.empty:
        raise FilterDeclarationError(
            f"Filter {func.__qualname__} must annotate its value parameter "
            f"{param.name!r}; the annotation is what the schema field is built from."
        )

    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception as exc:  # NameError, and whatever a bad forward ref raises
        raise FilterDeclarationError(
            f"Could not resolve the annotation of {func.__qualname__}: {exc}. "
            f"Names used in filter annotations must be importable at runtime, not "
            f"only under `if TYPE_CHECKING:`."
        ) from exc

    return hints.get(param.name, param.annotation)


_SpecT = TypeVar("_SpecT", FilterSpec, SortSpec)


def collect_specs(
    cls: type,
    reserved: frozenset[str],
    build: Callable[[str, Callable[..., Any]], _SpecT],
    kind: str = "filter",
) -> tuple[_SpecT, ...]:
    """Collect the filters -- or sorts -- declared on ``cls`` and its bases.

    Bases are walked in reverse MRO order so that inherited declarations keep their
    original position and a subclass redefining a name overrides it in place.
    """

    specs: dict[str, _SpecT] = {}
    # Everything the class itself answers to -- apply, statement, Schema and the rest.
    # From the live metaclass, so a namespace's own additions count too.
    provided = frozenset(name for name in dir(type(cls)) if not name.startswith("_"))

    for _cls in reversed(cls.__mro__):
        for name, member in _candidates(_cls, reserved, provided, kind):
            specs[name] = build(name, member)

    return tuple(specs.values())


def _candidates(
    cls: type,
    reserved: frozenset[str],
    provided: frozenset[str],
    kind: str,
) -> Iterator[tuple[str, Any]]:
    """Yield the ``(name, function)`` pairs of ``cls`` that look like filters or sorts."""

    for name, member in vars(cls).items():
        if name.startswith("_"):
            # Private helper, not a filter.
            continue

        if not inspect.isfunction(member):
            # Nested classes, constants, classmethods and properties are not filters.
            continue

        if name in reserved:
            raise FilterDeclarationError(
                f"{cls.__qualname__}.{name} cannot be a {kind}: {name!r} is one of "
                f"the methods a {kind} body calls on the statement "
                f"({', '.join(sorted(reserved))}), so type checkers would read it as "
                f"an override of that method rather than as a {kind}. Rename it."
                f"{_alias_hint(kind, name)}"
            )

        if name in provided:
            raise FilterDeclarationError(
                f"{cls.__qualname__}.{name} cannot be a {kind}: {name!r} is one of "
                f"the things the {'filters' if kind == 'filter' else 'sorting'} class "
                f"itself provides "
                f"({', '.join(sorted(provided))}), and a {kind} of that name would "
                f"shadow it. Rename it.{_alias_hint(kind, name)}"
            )

        yield name, member


def _alias_hint(kind: str, name: str) -> str:
    """How to keep a clashing filter's parameter name. A sort's name is a value, not a field."""

    if kind != "filter":
        return ""

    return (
        f" To keep {name!r} as the incoming parameter name, alias the field - "
        f"@options(alias={name!r}) on Pydantic, data_key={name!r} on Marshmallow."
    )


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Split ``T | None`` into ``(T, True)``; anything else into ``(annotation, False)``."""

    origin = getattr(annotation, "__origin__", None)

    if origin is Union or type(annotation).__name__ == "UnionType":
        args = [arg for arg in annotation.__args__ if arg is not type(None)]

        if len(args) < len(annotation.__args__):
            # reduce rather than Union[tuple(args)], for the same reason.
            return reduce(or_, args), True

    return annotation, False
