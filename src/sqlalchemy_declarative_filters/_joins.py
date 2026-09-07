"""What ``self`` is inside a filter body, and the join bookkeeping behind it.

SQLAlchemy does not deduplicate joins. ``select(Book).join(Author).join(Author)``
compiles to ``FROM book JOIN author ON ... JOIN author ON ...``, which most databases
reject and the rest answer wrongly. Two filters that both need the same join therefore
cannot each call ``.join()`` on the raw statement, and neither can a filter whose join
the caller already added before handing the statement over.

So filters are not handed the raw statement. They get a :class:`Statement`, which
forwards everything to it untouched except ``join``, which it deduplicates first. Every
filter in one ``apply`` shares the same record of what has been joined, seeded from the
statement that came in.

Deduplication is by identity, not by heuristic: ``inspect(target)`` followed by
``_deannotate()`` yields the very same object that walking ``get_final_froms()``
produces, aliases included.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.sql.selectable import FromClause, Join

from ._exceptions import JoinConflictWarning

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ("JoinTracker", "Statement", "existing_joins", "resolve_target")


@dataclass(frozen=True)
class _JoinInfo:
    """How a target was joined, so a later request for it can be compared."""

    onclause: Any = None
    isouter: bool = False
    full: bool = False

    def agrees_with(self, other: _JoinInfo) -> bool:
        """Whether ``other`` asks for the same kind of join as this one."""

        if (self.isouter, self.full) != (other.isouter, other.full):
            return False

        if self.onclause is None or other.onclause is None:
            # An inferred onclause is compatible with anything for the same target.
            return True

        return bool(self.onclause.compare(other.onclause))


class JoinTracker:
    """The joins one ``apply`` has available, shared by every filter it runs.

    The incoming statement's own from-list is only resolved if a filter actually asks
    for a join, because resolving it is the expensive part.
    """

    __slots__ = ("_known", "_statement")

    def __init__(self, statement: Any) -> None:
        self._statement = statement
        self._known: dict[FromClause, _JoinInfo | None] | None = None

    def claim(self, target: Any, requested: _JoinInfo) -> bool:
        """Record a join onto ``target``, and say whether it still needs applying.

        Returns ``False`` when the target is already in the from-list, whether a
        previous filter put it there or the caller did.
        """

        if self._known is None:
            self._known = existing_joins(self._statement)

        selectable = resolve_target(target)

        if selectable is None:
            # Unresolvable target: apply it and let SQLAlchemy have the final say.
            return True

        if selectable in self._known:
            _warn_on_conflict(self._known[selectable], requested, selectable)
            return False

        self._known[selectable] = requested

        return True


class Statement:
    """The statement being built, as a filter body sees it.

    Every attribute is the statement's own -- ``where``, ``having``, ``order_by`` and
    the rest behave exactly as they do on a SQLAlchemy ``Select``, and return another
    :class:`Statement` so they chain. The one addition is that ``join`` is idempotent:
    joining a target that is already in the from-list is a no-op rather than a
    duplicate.

    Methods whose result is no longer the statement being built -- ``subquery()``,
    ``scalar_subquery()``, ``exists()``, ``compile()`` -- return that result unwrapped.
    For the few places SQLAlchemy inspects the argument's type instead of calling a
    method on it, use :meth:`unwrap`.
    """

    __slots__ = ("_statement", "_tracker")

    def __init__(self, statement: Any, tracker: JoinTracker) -> None:
        self._statement = statement
        self._tracker = tracker

    def join(
        self,
        target: Any,
        onclause: Any = None,
        *,
        isouter: bool = False,
        full: bool = False,
    ) -> Statement:
        """Join ``target``, unless it is already joined.

        Deduplicated against the joins other filters in the same ``apply`` asked for
        and against the ones the incoming statement already carried. Targets are
        matched by the selectable they resolve to, so a mapped class, its relationship
        attribute and its ``__table__`` are one target, while two ``aliased()``
        constructs are two.
        """

        if not hasattr(self._statement, "join"):
            raise TypeError(
                f"{type(self._statement).__name__} does not support joins. Joins are "
                f"only available on Select statements; filter an Exists through a "
                f"correlated predicate such as Book.author.has(...) instead."
            )

        requested = _JoinInfo(onclause=onclause, isouter=isouter, full=full)

        if not self._tracker.claim(target, requested):
            return self

        arguments = (target,) if onclause is None else (target, onclause)

        joined = self._statement.join(*arguments, isouter=isouter, full=full)

        return cast("Statement", self._rewrap(joined))

    def outerjoin(self, target: Any, onclause: Any = None, *, full: bool = False) -> Statement:
        """``join(..., isouter=True)``, matching SQLAlchemy's spelling."""

        return self.join(target, onclause, isouter=True, full=full)

    def unwrap(self) -> Any:
        """The underlying SQLAlchemy statement.

        Needed where SQLAlchemy wants the statement itself rather than a builder --
        ``Book.id.in_(...)`` and ``union(...)`` check the argument's type and will
        not take the wrapper. Joins stay deduplicated afterwards: whatever a filter
        returns is re-wrapped with the same join record before the next one runs.
        """

        return self._statement

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._statement, name)

        if not callable(attribute):
            return attribute

        def method(*args: Any, **kwargs: Any) -> Any:
            return self._rewrap(attribute(*args, **kwargs))

        method.__name__ = name
        method.__doc__ = attribute.__doc__

        return method

    def __str__(self) -> str:
        return str(self._statement)

    def __repr__(self) -> str:
        return f"<Statement {self._statement!r}>"

    def _rewrap(self, result: Any) -> Any:
        """Keep the wrapper on results that are still the statement being built."""

        if isinstance(result, type(self._statement)):
            return Statement(result, self._tracker)

        # .subquery(), .scalar_subquery(), .compile() and friends are done with us.
        return result


def unwrap(value: Any) -> Any:
    """Return the SQLAlchemy statement behind ``value``, if it is wrapped."""

    return value.unwrap() if isinstance(value, Statement) else value


def resolve_target(target: Any) -> FromClause | None:
    """Reduce a join target to the canonical ``FromClause`` it will contribute.

    Accepts anything ``Select.join`` accepts: a mapped class, a relationship
    attribute, an ``aliased()`` construct, or a plain ``Table``. Returns ``None`` when
    the target cannot be resolved, in which case it must not be deduplicated.
    """

    if isinstance(target, FromClause):
        return _deannotate(target)

    try:
        inspected = sa_inspect(target)
    except NoInspectionAvailable:
        return None

    if inspected is None:
        return None

    # A relationship attribute (`Book.author`) resolves through its property's entity.
    prop = getattr(inspected, "property", None)
    entity = getattr(prop, "entity", None)

    if entity is not None:
        selectable = getattr(entity, "selectable", None)

        if isinstance(selectable, FromClause):
            return _deannotate(selectable)

    # A mapped class or an aliased() construct exposes the selectable directly.
    for attribute in ("selectable", "local_table", "persist_selectable"):
        candidate = getattr(inspected, attribute, None)

        if isinstance(candidate, FromClause):
            return _deannotate(candidate)

    return None


def existing_joins(statement: Any) -> dict[FromClause, _JoinInfo | None]:
    """Every ``FromClause`` the statement already selects from, and how it got there.

    ``get_final_froms()`` runs the ORM's from-list resolution, so joins added as
    ``.join(Author)`` show up here as real ``Join`` objects rather than as the
    unresolved entries kept on the private ``_setup_joins``. A selectable that is not
    joined at all -- the statement's base entity -- maps to ``None``.
    """

    found: dict[FromClause, _JoinInfo | None] = {}
    get_final_froms: Callable[[], list[FromClause]] | None = getattr(
        statement, "get_final_froms", None
    )

    if get_final_froms is None:
        # Exists and friends have no from-list to inspect.
        return found

    pending: list[tuple[FromClause, _JoinInfo | None]] = [
        (from_clause, None) for from_clause in get_final_froms()
    ]

    while pending:
        from_clause, info = pending.pop()

        if isinstance(from_clause, Join):
            joined = _JoinInfo(
                onclause=from_clause.onclause,
                isouter=from_clause.isouter,
                full=from_clause.full,
            )
            pending.append((from_clause.left, None))
            pending.append((from_clause.right, joined))
        else:
            found[_deannotate(from_clause)] = info

    return found


def _warn_on_conflict(
    previous: _JoinInfo | None,
    requested: _JoinInfo,
    selectable: FromClause,
) -> None:
    """Warn when a duplicate join asks for something other than what is in place."""

    if previous is None or previous.agrees_with(requested):
        # Either it is the statement's base entity, or the two requests agree.
        return

    warnings.warn(
        f"Conflicting joins onto {selectable!r}: kept isouter={previous.isouter}, "
        f"full={previous.full} from the join already in place and dropped "
        f"isouter={requested.isouter}, full={requested.full}. Make the two join() "
        f"calls agree, or alias the target so they are distinct joins.",
        JoinConflictWarning,
        stacklevel=4,
    )


def _deannotate(from_clause: FromClause) -> FromClause:
    """Strip ORM annotations so identity comparison works.

    The ORM wraps selectables in annotated proxies (``AnnotatedAlias`` and friends)
    when it builds the from-list. ``_deannotate()`` returns the underlying object,
    which is identical to the one ``inspect()`` hands back for the same target.
    """

    deannotate = getattr(from_clause, "_deannotate", None)

    return from_clause if deannotate is None else deannotate()
