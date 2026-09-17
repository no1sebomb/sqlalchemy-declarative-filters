"""The Pydantic backend."""

import datetime
import decimal

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from sqlalchemy_declarative_filters.pydantic import (
    Filters,
    OrderStyle,
    Params,
    PydanticFilters,
    PydanticParams,
    PydanticSorting,
    Sorting,
    deprecated,
    descending,
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


def test_deprecated_reaches_the_json_schema():
    class WithDeprecated(Filters):
        @deprecated(alternative="genres")
        def genre(self, value: Genre):
            """Books of this genre."""

            return self.where(Book.genre == value)

        def genres(self, value: list[Genre]):
            """Books of any of these genres."""

            return self.where(Book.genre.in_(value))

    properties = WithDeprecated.Schema.model_json_schema()["properties"]

    assert properties["genre"]["deprecated"] is True
    assert properties["genre"]["description"].endswith("Use 'genres' instead.")
    assert "deprecated" not in properties["genres"]


def test_a_deprecated_filter_still_applies_from_a_model():
    class WithDeprecated(Filters):
        @deprecated(alternative="genres")
        def genre(self, value: Genre):
            """Books of this genre."""

            return self.where(Book.genre == value)

    values = WithDeprecated.Schema(genre=Genre.POETRY)

    # `apply` reads the model through model_dump(), which does not trip Pydantic's
    # own deprecation warning on attribute access.
    assert "book.genre = " in sql(WithDeprecated.apply(select(Book), values))


def test_the_type_parameter_works_in_this_namespace_too():
    class Catalogue(Filters[Book]):
        """Filters that say what they filter."""

        def title(self, value: str):
            """Books whose title contains this."""

            return self.where(Book.title.ilike(f"%{value}%"))

    assert Catalogue.__model__ is Book
    assert "FROM book" in sql(Catalogue.statement({"title": "tomb"}))
    assert "lower(book.title) LIKE lower" in str(Catalogue.condition({"title": "tomb"}))


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


# --- sorting ----------------------------------------------------------------------------


class BookSorting(Sorting[Book]):
    """Orderings for the book catalogue."""

    __sort_field__ = "sort_by"
    __order_style__ = OrderStyle.ASC_FLAG
    __default_sort__ = "title"

    def title(self):
        """By title."""

        return self.order_by(Book.title)

    @descending
    def newest(self):
        """By release date."""

        return self.order_by(Book.released_on)


def test_sorting_is_the_pydantic_base():
    assert Sorting is PydanticSorting
    assert issubclass(BookSorting.Schema, BaseModel)
    assert list(BookSorting.Schema.model_fields) == ["sort_by", "asc"]


@pytest.mark.parametrize(("raw", "expected"), [("0", False), ("false", False), ("1", True)])
def test_a_flag_is_coerced_from_the_query_string(raw, expected):
    assert BookSorting.Schema(sort_by="newest", asc=raw).asc is expected


def test_an_unknown_sort_is_rejected_by_the_model():
    with pytest.raises(ValidationError, match="sort_by"):
        BookSorting.Schema(sort_by="isbn")


def test_apply_takes_the_sorting_model():
    values = BookSorting.Schema(sort_by="newest", asc="0")

    assert sql(BookSorting.apply(select(Book), values)).endswith(
        "ORDER BY book.released_on DESC, book.id DESC"
    )
    assert sql(BookSorting.apply(select(Book), BookSorting.Schema())).endswith(
        "ORDER BY book.title, book.id"
    )


def test_the_json_schema_offers_the_sorts_as_an_enum():
    properties = BookSorting.Schema.model_json_schema()["properties"]

    assert properties["sort_by"]["enum"] == ["title", "newest"]
    assert properties["sort_by"]["default"] == "title"
    assert "`newest`: By release date." in properties["sort_by"]["description"]
    assert properties["asc"]["anyOf"] == [{"type": "boolean"}, {"type": "null"}]


def test_a_prefix_sort_field_offers_both_directions():
    class Prefixed(BookSorting):
        __sort_field__ = "sort"
        __order_style__ = OrderStyle.PREFIX
        __default_sort__ = "newest"

    properties = Prefixed.Schema.model_json_schema()["properties"]

    assert list(properties) == ["sort"]
    assert properties["sort"]["enum"] == ["title", "-title", "newest", "-newest"]
    assert properties["sort"]["default"] == "-newest"


# --- params ------------------------------------------------------------------------------


class BookParams(Params[Book]):
    """Parameters for listing the book catalogue."""

    filters = BookFilters
    sorting = BookSorting


def test_params_is_the_pydantic_base():
    assert Params is PydanticParams
    assert issubclass(BookParams.Schema, BaseModel)


def test_the_params_json_schema_documents_every_field():
    schema = BookParams.Schema.model_json_schema()
    properties = schema["properties"]

    assert schema["description"] == "Parameters for listing the book catalogue."
    assert list(properties)[-2:] == ["sort_by", "asc"]
    assert properties["title"]["description"] == "Books whose title contains this."
    assert properties["title"]["examples"] == ["tomb"]
    assert properties["sort_by"]["enum"] == ["title", "newest"]


def test_the_params_model_validates_and_coerces_every_part():
    values = BookParams.Schema(title="tomb", availability="null", sort_by="newest", asc="0")

    assert values.availability is None
    assert values.asc is False

    with pytest.raises(ValidationError, match="title"):
        BookParams.Schema(title="ab")


def test_apply_takes_the_params_model_and_so_does_each_part():
    values = BookParams.Schema(title="tomb", sort_by="newest", asc="0")

    assert sql(BookParams.apply(select(Book), values)).endswith(
        "ORDER BY book.released_on DESC, book.id DESC"
    )
    assert "ORDER BY" not in sql(BookFilters.apply(select(Book), values))


def test_a_sorting_class_with_no_sorts_builds_an_empty_model():
    class EmptySorting(Sorting[Book]):
        """Nothing to order by yet."""

    class EmptyParams(Params[Book]):
        filters = BookFilters
        sorting = EmptySorting

    # An empty Literal is not a type Pydantic can build a field from, so neither the
    # sorting model nor the combined one gets a sort field at all.
    assert EmptySorting.Schema.model_fields == {}
    assert "sort_by" not in EmptyParams.Schema.model_fields
    assert "title" in EmptyParams.Schema.model_fields
