"""The Marshmallow backend."""

import datetime
import decimal
from typing import Literal

import pytest
from marshmallow import Schema, ValidationError, validate
from sqlalchemy import select

from sqlalchemy_declarative_filters.marshmallow import (
    Filters,
    MarshmallowFilters,
    options,
    skip_null,
)

from .conftest import Author, Availability, Book, Genre, sql


class BookFilters(Filters):
    """Parameters for filtering the book catalogue."""

    def ids(self, value: list[int]):
        """Only books with one of these IDs."""

        return self.where(Book.id.in_(value))

    @options(validate=validate.Length(min=3), data_key="q")
    def title(self, value: str):
        """Books whose title contains this."""

        return self.where(Book.title.ilike(f"%{value}%"))

    def genre(self, value: Genre):
        """Books of this genre."""

        return self.where(Book.genre == value)

    def genres(self, value: list[Genre]):
        """Books of any of these genres."""

        return self.where(Book.genre.in_(value))

    @options(validate=validate.Range(min=1400, max=2100))
    def published_after(self, value: int):
        """Books first published after this year."""

        return self.where(Book.published_in > value)

    def max_price(self, value: decimal.Decimal):
        """Books at most this expensive."""

        return self.where(Book.price <= value)

    def released_after(self, value: datetime.date):
        """Books released after this date."""

        return self.where(Book.released_on > value)

    def has_publisher(self, value: bool):
        """Books that do, or do not, have a publisher."""

        return self.where(Book.publisher_id.is_not(None) if value else Book.publisher_id.is_(None))

    def sort_hint(self, value: Literal["title", "year"]):
        """Recorded, not applied; here to exercise Literal mapping."""

        return self

    def author_name(self, value: str):
        """Books whose author's name contains this."""

        return self.join(Book.author).where(Author.name.ilike(f"%{value}%"))

    @skip_null
    def availability(self, value: Availability = Availability.IN_PRINT):
        """Books with this availability. Pass null for any."""

        return self.where(Book.availability == value)


def test_filters_is_the_marshmallow_base():
    assert Filters is MarshmallowFilters
    assert BookFilters.__backend__ == "marshmallow"


def test_schema_is_a_marshmallow_schema():
    schema = BookFilters.Schema

    assert issubclass(schema, Schema)
    assert schema.__name__ == "BookFiltersSchema"


@pytest.mark.parametrize(
    ("name", "field_type"),
    [
        ("ids", "List"),
        ("title", "String"),
        ("genre", "Enum"),
        ("genres", "List"),
        ("published_after", "Integer"),
        ("max_price", "Decimal"),
        ("released_after", "Date"),
        ("has_publisher", "Boolean"),
        ("sort_hint", "Raw"),
        ("availability", "Enum"),
    ],
)
def test_annotations_map_onto_field_types(name, field_type):
    assert type(BookFilters.Schema().fields[name]).__name__ == field_type


def test_container_annotations_map_their_inner_type():
    fields = BookFilters.Schema().fields

    assert type(fields["ids"].inner).__name__ == "Integer"
    assert type(fields["genres"].inner).__name__ == "Enum"


def test_a_literal_becomes_a_one_of_validator():
    field = BookFilters.Schema().fields["sort_hint"]

    assert [type(v).__name__ for v in field.validators] == ["OneOf"]

    with pytest.raises(ValidationError, match="Must be one of"):
        BookFilters.Schema().load({"sort_hint": "pages"})


def test_docstring_becomes_the_field_metadata():
    metadata = BookFilters.Schema().fields["title"].metadata

    assert metadata["description"] == "Books whose title contains this."


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"q": "ab"}, "Shorter than minimum"),
        ({"published_after": 1200}, "Must be greater than or equal to 1400"),
    ],
)
def test_options_reach_the_marshmallow_field(values, message):
    with pytest.raises(ValidationError, match=message):
        BookFilters.Schema().load(values)


def test_data_key_renames_the_incoming_parameter():
    assert BookFilters.Schema().load({"q": "tomb"})["title"] == "tomb"


@pytest.mark.parametrize(
    ("raw", "name", "expected"),
    [
        ({"ids": ["1", "2"]}, "ids", [1, 2]),
        ({"genre": "poetry"}, "genre", Genre.POETRY),
        ({"genres": ["poetry", "history"]}, "genres", [Genre.POETRY, Genre.HISTORY]),
        ({"max_price": "9.99"}, "max_price", decimal.Decimal("9.99")),
        ({"released_after": "2020-01-31"}, "released_after", datetime.date(2020, 1, 31)),
        ({"has_publisher": "false"}, "has_publisher", False),
    ],
)
def test_query_string_values_are_coerced(raw, name, expected):
    assert BookFilters.Schema().load(raw)[name] == expected


def test_enums_load_by_value():
    loaded = BookFilters.Schema().load({"availability": "out_of_print"})

    assert loaded["availability"] is Availability.OUT_OF_PRINT


def test_load_fills_in_defaults():
    values = BookFilters.Schema().load({})

    assert values["availability"] is Availability.IN_PRINT
    assert values["ids"] is None


@pytest.mark.parametrize("raw", ["", "null", "NONE", " Null "])
def test_null_strings_become_none(raw):
    assert BookFilters.Schema().load({"availability": raw})["availability"] is None


def test_null_strings_only_apply_to_skip_null_filters():
    with pytest.raises(ValidationError, match="genre"):
        BookFilters.Schema().load({"genre": "null"})


def test_apply_takes_the_loaded_dict():
    values = BookFilters.Schema().load({"q": "tomb"})
    compiled = sql(BookFilters.apply(select(Book), values))

    assert "lower(book.title) LIKE lower" in compiled
    assert "book.availability = " in compiled


def test_joins_are_planned_from_a_loaded_dict_too():
    values = BookFilters.Schema().load({"author_name": "borges"})
    statement = BookFilters.apply(select(Book).join(Book.author), values)

    assert sql(statement).count("JOIN author") == 1


def test_unknown_keys_are_excluded_rather_than_raising():
    assert "isbn" not in BookFilters.Schema().load({"isbn": "978-0"})


def test_a_multi_member_union_falls_back_to_a_raw_field():
    class Loose(Filters):
        """A union the mapping cannot narrow."""

        def isbn(self, value: str | int):
            """Books with this ISBN, however it was typed."""

            return self.where(Book.title == str(value))

    field = Loose.Schema().fields["isbn"]

    assert type(field).__name__ == "Raw"
    # Optional is stripped, the remaining members are kept.
    assert Loose.Schema().load({"isbn": 9780})["isbn"] == 9780
