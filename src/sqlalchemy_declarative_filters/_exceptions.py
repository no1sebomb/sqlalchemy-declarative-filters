"""Exception and warning types raised by the library."""

from __future__ import annotations

__all__ = (
    "BackendNotAvailableError",
    "FilterConditionError",
    "FilterDeclarationError",
    "FilterError",
    "JoinConflictWarning",
    "RedundantSkipNullWarning",
    "UnknownFilterError",
)


class FilterError(Exception):
    """Base class for every error raised by this library."""


class FilterDeclarationError(FilterError, TypeError):
    """A filter method is declared incorrectly.

    Raised while the schema is being built, not while it is being applied.
    """


class FilterConditionError(FilterError):
    """The applied filters cannot be reduced to a bare ``WHERE`` clause.

    Raised by ``condition()`` when a filter adds a join or a ``HAVING`` clause: those
    live on the statement, not in the clause, so there is nothing to hand back. Use
    ``query()`` or ``apply()``, which return the statement itself.
    """


class UnknownFilterError(FilterError, KeyError):
    """A value was supplied for a name that is not a filter on the class."""

    def __str__(self) -> str:
        # KeyError.__str__ wraps the message in quotes; undo that.
        return str(self.args[0]) if self.args else ""


class BackendNotAvailableError(FilterError, ImportError):
    """A schema backend was requested but its optional dependency is missing."""


class JoinConflictWarning(UserWarning):
    """A join was requested onto a target that is already joined another way.

    The join already in place wins, whether an earlier filter added it or the caller
    did before handing the statement over. Make the ``self.join(...)`` calls agree, or
    alias the target so the two joins address distinct selectables.
    """


class RedundantSkipNullWarning(UserWarning):
    """``@skip_null`` was applied to a filter that declares no default.

    Such a filter is already skipped when its value is ``None``, so the decorator
    changes nothing. Give the value parameter a default if the filter was meant to
    apply on its own, or drop the decorator.
    """
