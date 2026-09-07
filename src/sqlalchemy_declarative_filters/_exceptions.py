"""Exception and warning types raised by the library."""

from __future__ import annotations

__all__ = (
    "BackendNotAvailableError",
    "FilterDeclarationError",
    "FilterError",
    "JoinConflictWarning",
    "UnknownFilterError",
)


class FilterError(Exception):
    """Base class for every error raised by this library."""


class FilterDeclarationError(FilterError, TypeError):
    """A filter method is declared incorrectly.

    Raised while the schema is being built, not while it is being applied.
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
