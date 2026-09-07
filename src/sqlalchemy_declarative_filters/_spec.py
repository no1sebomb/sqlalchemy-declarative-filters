"""Introspection of filter classes into plain, backend-agnostic descriptions.

Nothing in this module knows about dataclasses, Pydantic or Marshmallow. It turns
a class body full of decorated methods into :class:`FilterSpec` objects, which the
schema backends then render.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, Any, Union, get_type_hints

from ._exceptions import FilterDeclarationError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

__all__ = ("FilterSpec", "collect_specs", "unwrap_optional")

#: Attribute names the decorators write onto filter methods.
OPTIONS_ATTR = "__filter_options__"
SKIP_NULL_ATTR = "__filter_skip_null__"


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
        )


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


def collect_specs(cls: type, reserved: frozenset[str]) -> tuple[FilterSpec, ...]:
    """Collect the filters declared on ``cls`` and everything it inherits from.

    Bases are walked in reverse MRO order so that inherited filters keep their
    original position and a subclass redefining a name overrides it in place.
    """

    specs: dict[str, FilterSpec] = {}

    for _cls in reversed(cls.__mro__):
        for name, member in _candidates(_cls, reserved):
            specs[name] = FilterSpec.from_function(name, member)

    return tuple(specs.values())


def _candidates(cls: type, reserved: frozenset[str]) -> Iterator[tuple[str, Any]]:
    """Yield the ``(name, function)`` pairs of ``cls`` that look like filters."""

    for name, member in vars(cls).items():
        if name.startswith("_"):
            # Private helper, not a filter.
            continue

        if not inspect.isfunction(member):
            # Nested classes, constants, classmethods and properties are not filters.
            continue

        if name in reserved:
            raise FilterDeclarationError(
                f"{cls.__qualname__}.{name} cannot be a filter: {name!r} is one of "
                f"the methods a filter body calls on the statement "
                f"({', '.join(sorted(reserved))}), so type checkers would read it as "
                f"an override of that method rather than as a filter. Rename it. To "
                f"keep {name!r} as the incoming parameter name, alias the field - "
                f"@options(alias={name!r}) on Pydantic, data_key={name!r} on "
                f"Marshmallow."
            )

        yield name, member


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Split ``T | None`` into ``(T, True)``; anything else into ``(annotation, False)``."""

    origin = getattr(annotation, "__origin__", None)

    if origin is Union or type(annotation).__name__ == "UnionType":
        args = [arg for arg in annotation.__args__ if arg is not type(None)]

        if len(args) < len(annotation.__args__):
            # reduce rather than Union[tuple(args)], for the same reason.
            return reduce(or_, args), True

    return annotation, False
