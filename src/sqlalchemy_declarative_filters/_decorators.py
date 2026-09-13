"""Decorators applied to filter methods.

Each decorator only records intent on the function object. Nothing is validated or
built here; that happens once, lazily, when a schema is first requested.

``options`` is deliberately untyped at runtime: the keywords it accepts depend on the
schema backend in use, and each backend namespace ships a stub that pins them down.
"""

from __future__ import annotations

import inspect
import warnings
from typing import TYPE_CHECKING, Any, TypeVar

from ._exceptions import RedundantSkipNullWarning
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
    value is ``None``, so applying it there warns with
    :class:`~._exceptions.RedundantSkipNullWarning`.
    """

    _warn_if_redundant(func)
    setattr(func, SKIP_NULL_ATTR, True)

    return func


def _warn_if_redundant(func: Callable[..., Any]) -> None:
    """Warn when ``@skip_null`` is decorating a filter that has no default.

    Checked here rather than when the schema is built so that the warning points at
    the decorator itself. A signature this cannot read, or one that is not shaped like
    a filter at all, is left alone: :meth:`~._spec.FilterSpec.from_function` reports
    those properly once the class is used.
    """

    try:
        params = list(inspect.signature(func).parameters.values())[1:]  # drop `self`
    except (TypeError, ValueError):  # pragma: no cover - unreadable signature
        return

    if len(params) != 1 or params[0].default is not inspect.Parameter.empty:
        return

    warnings.warn(
        f"@skip_null does nothing on {func.__qualname__}: the filter declares no "
        f"default, so it is already skipped when its value is None. Give "
        f"{params[0].name!r} a default to have something for null to switch off, or "
        f"drop the decorator.",
        RedundantSkipNullWarning,
        # _warn_if_redundant <- skip_null <- the decorated class body.
        stacklevel=3,
    )
