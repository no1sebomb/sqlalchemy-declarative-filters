"""Shared ORM models for the test suite: a small library catalogue.

Publisher 1--* Book *--1 Author, Book 1--* Review, Book *--* Tag. Between them they
cover every join shape a filter can ask for: many-to-one, one-to-many, many-to-many,
and a nullable side worth an outer join.
"""

import datetime
import decimal
import enum

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Genre(str, enum.Enum):
    FICTION = "fiction"
    HISTORY = "history"
    POETRY = "poetry"
    SCIENCE = "science"


class Availability(str, enum.Enum):
    IN_PRINT = "in_print"
    OUT_OF_PRINT = "out_of_print"
    ANNOUNCED = "announced"


book_tag = sa.Table(
    "book_tag",
    Base.metadata,
    sa.Column("book_id", sa.ForeignKey("book.id"), primary_key=True),
    sa.Column("tag_id", sa.ForeignKey("tag.id"), primary_key=True),
)


class Author(Base):
    __tablename__ = "author"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    country: Mapped[str]
    born_in: Mapped[int]
    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Publisher(Base):
    __tablename__ = "publisher"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    country: Mapped[str]
    books: Mapped[list["Book"]] = relationship(back_populates="publisher")


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    books: Mapped[list["Book"]] = relationship(secondary=book_tag, back_populates="tags")


class Book(Base):
    __tablename__ = "book"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    genre: Mapped[Genre]
    availability: Mapped[Availability] = mapped_column(default=Availability.IN_PRINT)
    published_in: Mapped[int]
    pages: Mapped[int]
    price: Mapped[decimal.Decimal] = mapped_column(sa.Numeric(8, 2))
    released_on: Mapped[datetime.date]
    author_id: Mapped[int] = mapped_column(sa.ForeignKey("author.id"))
    # Nullable, so filtering on it wants an outer join.
    publisher_id: Mapped[int | None] = mapped_column(sa.ForeignKey("publisher.id"))

    author: Mapped[Author] = relationship(back_populates="books")
    publisher: Mapped[Publisher | None] = relationship(back_populates="books")
    tags: Mapped[list[Tag]] = relationship(secondary=book_tag, back_populates="books")
    reviews: Mapped[list["Review"]] = relationship(back_populates="book")


class Review(Base):
    __tablename__ = "review"

    id: Mapped[int] = mapped_column(primary_key=True)
    rating: Mapped[int]
    body: Mapped[str]
    book_id: Mapped[int] = mapped_column(sa.ForeignKey("book.id"))
    book: Mapped[Book] = relationship(back_populates="reviews")


def sql(statement) -> str:
    """Compile a statement to a single-line SQL string for assertions."""

    return " ".join(str(statement).split())
