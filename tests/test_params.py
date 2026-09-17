"""Params: filters and sorting combined behind one schema."""

import dataclasses

import pytest
from sqlalchemy import func, select

from sqlalchemy_declarative_filters import (
    FilterDeclarationError,
    Filters,
    OrderStyle,
    Params,
    Sorting,
    UnknownFilterError,
    UnknownSortError,
    descending,
    skip_null,
)

from .conftest import Author, Availability, Book, Genre, sql


class BookFilters(Filters[Book]):
    """Parameters for filtering the book catalogue."""

    def title(self, value: str):
        """Books whose title contains this."""

        return self.where(Book.title.ilike(f"%{value}%"))

    def author_name(self, value: str):
        """Books whose author's name is this."""

        return self.join(Book.author).where(Author.name == value)

    @skip_null
    def availability(self, value: Availability = Availability.IN_PRINT):
        """Books with this availability. Pass null for any."""

        return self.where(Book.availability == value)


class GenreFilters(Filters[Book]):
    """A second filters part."""

    def genre(self, value: Genre):
        """Books of this genre."""

        return self.where(Book.genre == value)


class BookSorting(Sorting[Book]):
    """Orderings for the book catalogue."""

    __order_style__ = OrderStyle.PREFIX
    __default_sort__ = "released"

    def author(self):
        """By author's name."""

        return self.join(Book.author).order_by(Author.name)

    @descending
    def released(self):
        """By release date."""

        return self.order_by(Book.released_on)


class BookParams(Params[Book]):
    """Parameters for listing the book catalogue."""

    filters = BookFilters
    sorting = BookSorting


def where_and_order(statement) -> str:
    """Everything from WHERE on, or from ORDER BY when there is no WHERE."""

    compiled = sql(statement)

    return compiled[
        compiled.index(" WHERE ") if " WHERE " in compiled else compiled.index(" ORDER BY ") :
    ]


# --- declaration ----------------------------------------------------------------------


def test_the_parts_are_the_public_attributes_in_declaration_order():
    assert BookParams.__parts__ == {"filters": BookFilters, "sorting": BookSorting}


def test_the_schema_has_every_parts_fields_and_the_params_docstring():
    schema = BookParams.Schema

    assert schema.__name__ == "BookParamsSchema"
    assert schema.__doc__ == "Parameters for listing the book catalogue."
    assert [field.name for field in dataclasses.fields(schema)] == [
        "title",
        "author_name",
        "availability",
        "sort",
    ]


def test_the_fields_follow_declaration_order_not_part_kind():
    class SortingFirst(Params[Book]):
        sorting = BookSorting
        filters = BookFilters

    assert dataclasses.fields(SortingFirst.Schema)[0].name == "sort"


def test_parts_are_inherited_and_replaced_in_place():
    class MoreBookFilters(BookFilters):
        def min_pages(self, value: int):
            """Books at least this long."""

            return self.where(Book.pages >= value)

    class Extended(BookParams):
        filters = MoreBookFilters
        genres = GenreFilters

    assert Extended.__parts__ == {
        "filters": MoreBookFilters,
        "sorting": BookSorting,
        "genres": GenreFilters,
    }

    compiled = sql(Extended.statement({"min_pages": 100, "genre": Genre.POETRY}))

    assert "book.pages >= " in compiled
    assert "book.genre = " in compiled


def test_a_part_must_be_a_filters_or_sorting_class():
    class Instance(Params):
        filters = BookFilters.Schema

    with pytest.raises(FilterDeclarationError, match="not a Filters or Sorting class"):
        _ = Instance.__parts__


def test_a_part_cannot_shadow_what_the_class_provides():
    Shadowing = type("Shadowing", (Params,), {"statement": BookFilters})

    with pytest.raises(FilterDeclarationError, match="the params class itself provides"):
        _ = Shadowing.__parts__


def test_only_one_sorting_part():
    class TwoWays(BookParams):
        other = BookSorting

    with pytest.raises(FilterDeclarationError, match="more than one sorting part"):
        _ = TwoWays.__parts__


def test_two_parts_cannot_read_the_same_field():
    class TitleSorting(Sorting[Book]):
        __sort_field__ = "title"

        def pages(self):
            """By length."""

            return self.order_by(Book.pages)

    class Clashing(Params[Book]):
        filters = BookFilters
        sorting = TitleSorting

    with pytest.raises(FilterDeclarationError, match="both read a field named 'title'"):
        _ = Clashing.Schema


def test_the_parts_must_be_over_the_same_model():
    class AuthorFilters(Filters[Author]):
        def name(self, value: str):
            return self.where(Author.name == value)

    class Mixed(Params[Book]):
        filters = AuthorFilters

    with pytest.raises(FilterDeclarationError, match="is over Author"):
        _ = Mixed.__parts__


# --- applying ---------------------------------------------------------------------------


def test_apply_runs_the_filters_then_the_sorting():
    statement = BookParams.statement({"title": "tomb", "author_name": "borges", "sort": "-author"})
    compiled = sql(statement)

    assert compiled.count("JOIN author") == 1
    assert where_and_order(statement) == (
        " WHERE lower(book.title) LIKE lower(:title_1) AND author.name = :name_1 "
        "AND book.availability = :availability_1 ORDER BY author.name DESC, book.id DESC"
    )


def test_each_part_keeps_its_own_defaults():
    statement = BookParams.statement(None)

    assert where_and_order(statement) == (
        " WHERE book.availability = :availability_1 ORDER BY book.released_on DESC, book.id DESC"
    )


def test_apply_takes_a_schema_instance_and_null_strings_still_switch_defaults_off():
    values = BookParams.Schema.from_mapping({"availability": "null", "sort": "author"})

    assert where_and_order(BookParams.apply(select(Book), values)) == (
        " ORDER BY author.name, book.id"
    )


def test_an_unknown_parameter_is_reported():
    with pytest.raises(UnknownFilterError, match="BookParams has no parameter"):
        BookParams.statement({"isbn": "978-0"})


def test_a_part_reads_only_its_own_fields_from_a_params_schema_instance():
    values = BookParams.Schema(title="tomb", sort="-author")

    filtered = sql(BookFilters.statement(values))
    ordered = sql(BookSorting.statement(values))

    assert "ORDER BY" not in filtered
    assert "lower(book.title) LIKE" in filtered
    assert "WHERE" not in ordered
    assert ordered.endswith("ORDER BY author.name DESC, book.id DESC")


def test_a_count_query_uses_the_filters_part_alone():
    values = BookParams.Schema(title="tomb", sort="-author")
    total = select(func.count()).select_from(BookFilters.statement(values).subquery())

    assert "ORDER BY" not in sql(total)


def test_a_part_still_refuses_a_plain_mapping_of_every_field():
    with pytest.raises(UnknownFilterError, match="no filter"):
        BookFilters.statement({"title": "tomb", "sort": "-author"})

    with pytest.raises(UnknownSortError, match="no field"):
        BookSorting.statement({"title": "tomb", "sort": "-author"})


def test_a_class_that_is_not_a_part_is_told_so():
    values = BookParams.Schema(title="tomb")

    with pytest.raises(TypeError, match="GenreFilters is not one of them"):
        GenreFilters.apply(select(Book), values)


def test_statement_without_a_model_says_how_to_give_it_one():
    class Anonymous(Params):
        filters = BookFilters

    with pytest.raises(FilterDeclarationError, match=r"Anonymous\(Params\[Book\]\)"):
        Anonymous.statement({})
