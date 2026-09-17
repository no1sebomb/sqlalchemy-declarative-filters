"""Fixture for :mod:`tests.test_typing`; not part of the package's own mypy run.

Every line marked ``# type-error`` must be rejected by a type checker, and every
other line must be accepted. ``tests/test_typing.py`` runs mypy over this file and
holds it to exactly that.
"""

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sqlalchemy_declarative_filters import Filters, OrderStyle, Sorting, Statement


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "book"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]


class Author(Base):
    __tablename__ = "author"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class BookFilters(Filters[Book]):
    """Filters that say what they filter."""

    def title(self, value: str) -> Statement:
        """Books whose title contains this."""

        return self.where(Book.title.ilike(f"%{value}%"))


class LooseFilters(Filters):
    """Filters that do not, and so are checked no more than they used to be."""

    def title(self, value: str) -> Statement:
        """Books whose title contains this."""

        return self.where(Book.title.ilike(f"%{value}%"))


values = {"title": "tomb"}

# The statement selects what the class filters.
book_statement: sa.Select[tuple[Book]] = BookFilters.apply(sa.select(Book), values)
book_built: sa.Select[tuple[Book]] = BookFilters.statement(values)
book_condition: sa.ColumnElement[bool] = BookFilters.condition(values)
sa.select(Book).where(BookFilters.condition(values))

# It does not. Written the way the statement usually reaches `apply`: as a variable,
# which is what gives the checker a type to disagree with. Inlined instead, as
# `apply(sa.select(Author), ...)`, SQLAlchemy's own `select` overloads fall back to
# `Select[Any]` under an expected type and the mismatch goes unreported.
other_statement = sa.select(Author)
BookFilters.apply(other_statement, values)  # type-error

# An unparameterised class still takes anything, as it did before.
author_statement: sa.Select[tuple[Author]] = LooseFilters.apply(other_statement, values)

# Statements that are not a select of the model keep their own type.
narrowed: sa.Exists = BookFilters.apply(sa.exists(sa.select(Book)), values)

# The return type follows the statement, not the other way round.
wrong_return: sa.Select[tuple[Author]] = BookFilters.statement(values)  # type-error


class BookSorting(Sorting[Book]):
    """Sorting that says what it sorts."""

    __sort_field__ = "sort_by"
    __order_style__ = OrderStyle.ASC_FLAG

    def title(self) -> Statement:
        """By title."""

        return self.order_by(Book.title)


class LooseSorting(Sorting):
    """Sorting that does not."""

    __sort_field__ = 1  # type-error

    def title(self) -> Statement:
        """By title."""

        return self.order_by(Book.title)


sort_values = {"sort_by": "title", "asc": False}

sorted_statement: sa.Select[tuple[Book]] = BookSorting.apply(sa.select(Book), sort_values)
sorted_built: sa.Select[tuple[Book]] = BookSorting.statement(sort_values)
BookSorting.apply(other_statement, sort_values)  # type-error
loose_sorted: sa.Select[tuple[Author]] = LooseSorting.apply(other_statement, sort_values)

# Filtering and sorting compose: each hands back the statement type it was given.
page: sa.Select[tuple[Book]] = BookSorting.apply(BookFilters.statement(values), sort_values)


# A subclass may pick another style than its base did.
class PrefixSorting(BookSorting):
    __order_style__ = OrderStyle.PREFIX


# The style is an OrderStyle, so a misspelling cannot get past the checker.
class StringlySorting(BookSorting):
    __order_style__ = "prefix"  # type-error
