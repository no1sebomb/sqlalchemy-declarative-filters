"""The Pydantic backend."""

import datetime
import decimal

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from sqlalchemy_declarative_filters.pydantic import (
    Filters,
    PydanticFilters,
    options,
    skip_null,
)

from .conftest import Author, Availability, Book, Genre, sql


class BookFilters(Filters):
    """Parameters for filtering the book catalogue."""

    def ids(self, value: list[int]):
        """Only books with one of these IDs."""

        return self.where(Book.id.in_(value))

    @options(min_length=3, examples=["tomb"])
    def title(self, value: str):
        """Books whose title contains this."""

        return self.where(Book.title.ilike(f"%{value}%"))

    def genre(self, value: Genre):
        """Books of this genre."""

        return self.where(Book.genre == value)

    def genres(self, value: list[Genre]):
        """Books of any of these genres."""

        return self.where(Book.genre.in_(value))

    @options(ge=1400, le=2100)
    def published_after(self, value: int):
        """Books first published after this year."""

        return self.where(Book.published_in > value)

    @options(gt=0)
    def max_price(self, value: decimal.Decimal):
        """Books at most this expensive."""

        return self.where(Book.price <= value)

    def released_after(self, value: datetime.date):
        """Books released after this date."""

        return self.where(Book.released_on > value)

    def author_name(self, value: str):
        """Books whose author's name contains this."""

        return self.join(Book.author).where(Author.name.ilike(f"%{value}%"))

    @skip_null
    def availability(self, value: Availability = Availability.IN_PRINT):
        """Books with this availability. Pass null for any."""

        return self.where(Book.availability == value)


def test_filters_is_the_pydantic_base():
    assert Filters is PydanticFilters
    assert BookFilters.__backend__ == "pydantic"


def test_schema_is_a_pydantic_model():
    schema = BookFilters.Schema

    assert issubclass(schema, BaseModel)
    assert schema.__name__ == "BookFiltersSchema"
    assert list(schema.model_fields) == [
        "ids",
        "title",
        "genre",
        "genres",
        "published_after",
        "max_price",
        "released_after",
        "author_name",
        "availability",
    ]


def test_docstring_becomes_the_field_description():
    fields = BookFilters.Schema.model_fields

    assert fields["title"].description == "Books whose title contains this."
    assert fields["genre"].description == "Books of this genre."


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"title": "ab"}, "at least 3 characters"),
        ({"published_after": 1200}, "greater than or equal to 1400"),
        ({"published_after": 2200}, "less than or equal to 2100"),
        ({"max_price": 0}, "greater than 0"),
    ],
)
def test_options_reach_pydantic_field(values, message):
    with pytest.raises(ValidationError, match=message):
        BookFilters.Schema(**values)


def test_json_schema_carries_the_declarations():
    properties = BookFilters.Schema.model_json_schema()["properties"]

    assert properties["title"]["examples"] == ["tomb"]
    assert properties["published_after"]["anyOf"][0]["minimum"] == 1400


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"ids": ["1", "2"]}, [1, 2]),
        ({"genre": "poetry"}, Genre.POETRY),
        ({"genres": ["poetry", "history"]}, [Genre.POETRY, Genre.HISTORY]),
        ({"max_price": "9.99"}, decimal.Decimal("9.99")),
        ({"released_after": "2020-01-31"}, datetime.date(2020, 1, 31)),
    ],
)
def test_query_string_values_are_coerced(raw, expected):
    name = next(iter(raw))

    assert getattr(BookFilters.Schema(**raw), name) == expected


def test_an_unparseable_value_is_rejected():
    with pytest.raises(ValidationError, match="genre"):
        BookFilters.Schema(genre="cookbook")


def test_defaults_come_from_the_annotation():
    values = BookFilters.Schema()

    assert values.availability is Availability.IN_PRINT
    assert values.ids is None


@pytest.mark.parametrize("raw", ["", "null", "NONE", " Null "])
def test_null_strings_become_none(raw):
    assert BookFilters.Schema(availability=raw).availability is None


def test_null_strings_only_apply_to_skip_null_filters():
    with pytest.raises(ValidationError):
        BookFilters.Schema(genre="null")


def test_apply_takes_the_model():
    values = BookFilters.Schema(title="tomb")
    compiled = sql(BookFilters.apply(select(Book), values))

    assert "lower(book.title) LIKE lower" in compiled
    # The declared default still applies; nothing was excluded as "unset".
    assert "book.availability = " in compiled


def test_joins_are_planned_from_a_model_too():
    values = BookFilters.Schema(author_name="borges")
    statement = BookFilters.apply(select(Book).join(Book.author), values)

    assert sql(statement).count("JOIN author") == 1


def test_other_backends_stay_reachable():
    import dataclasses

    class Plain(Filters):
        """No backend-specific options, so every backend can render it."""

        def ids(self, value: list[int]):
            """Only books with one of these IDs."""

            return self.where(Book.id.in_(value))

    assert dataclasses.is_dataclass(Plain.Dataclass)
    assert issubclass(Plain.Pydantic, BaseModel)
    assert Plain.Pydantic is Plain.Schema


def test_backend_specific_options_fail_loudly_on_another_backend():
    from sqlalchemy_declarative_filters import FilterDeclarationError

    with pytest.raises(FilterDeclarationError, match="same namespace"):
        _ = BookFilters.Dataclass
