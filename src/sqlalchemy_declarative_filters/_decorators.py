"""Decorators applied to filter methods.

Each decorator only records intent on the function object. Nothing is validated or
built here; that happens once, lazily, when a schema is first requested.

``options`` is deliberately untyped at runtime: the keywords it accepts depend on the
schema backend in use, and each backend namespace ships a stub that pins them down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from ._spec import OPTIONS_ATTR, SKIP_NULL_ATTR

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("options", "skip_null")

_FuncT = TypeVar("_FuncT", bound="Callable[..., Any]")


def options(**kwargs: Any) -> Callable[[_FuncT], _FuncT]:
    """Attach schema field options to a filter.

    The keywords are handed to the active backend verbatim, so they are whatever that
    backend's field constructor takes. Import ``options`` from the same namespace as
    ``Filters`` and your editor will hint the right ones.
    """

    def decorator(func: _FuncT) -> _FuncT:
        existing = dict(getattr(func, OPTIONS_ATTR, {}))
        existing.update(kwargs)
        setattr(func, OPTIONS_ATTR, existing)

        return func

    return decorator


def skip_null(func: _FuncT) -> _FuncT:
    """Let an explicit ``null`` switch off a filter that has a default.

    Without it, a filter declaring ``value: Status = Status.ACTIVE`` always applies.
    With it, the schema field accepts ``None`` -- and the strings ``""``, ``"null"``
    and ``"none"``, so a query string can say it too -- and the filter is skipped.

    It does nothing on a filter without a default, which is already skipped when its
    value is ``None``.
    """

    setattr(func, SKIP_NULL_ATTR, True)

    return func
