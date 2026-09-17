"""Sorting: declaration, direction, the order styles, and the dataclass schema."""

import dataclasses
import typing

import pytest
from sqlalchemy import exists, func, select

from sqlalchemy_declarative_filters import (
    FilterDeclarationError,
    Filters,
    InvalidOrderError,
    OrderStyle,
    Sorting,
    Statement,
    UnknownSortError,
    deprecated,
    descending,
    options,
    skip_null,
)

from .conftest import Author, Book, Publisher, Review, sql

AVERAGE_RATING = select(func.avg(Review.rating)).where(Review.book_id == Book.id).scalar_subquery()


class BookSorting(Sorting[Book]):
    """Orderings for the book catalogue."""

    def title(self):
        """By title."""

        return self.order_by(Book.title)

    def author(self):
        """By author's name, then the newest book first.

        The second paragraph stays out of the field description.
        """

        return self.join(Book.author).order_by(Author.name, Book.released_on.desc())

    def publisher(self):
        """By publisher's name, books without one last."""

        return self.outerjoin(Book.publisher).order_by(Publisher.name.nulls_last())

    @descending
    def rating(self):
        """By average review score."""

        return self.order_by(AVERAGE_RATING.nulls_last())

    @deprecated(alternative="title")
    def name(self):
        """By title, under its old name."""

        return self.order_by(Book.title)


def order_by(statement) -> str:
    """The ORDER BY clause of a compiled statement."""

    return sql(statement).split(" ORDER BY ", 1)[1]


# --- declaration ----------------------------------------------------------------------


def test_every_public_method_is_a_sort_in_declaration_order():
    assert [spec.name for spec in BookSorting.__sorts__] == [
        "title",
        "author",
        "publisher",
        "rating",
        "name",
    ]


def test_descending_and_deprecated_are_recorded():
    specs = {spec.name: spec for spec in BookSorting.__sorts__}

    assert specs["rating"].descending
    assert not specs["title"].descending
    assert specs["name"].deprecation_message == (
        "The 'name' sort is deprecated. Use 'title' instead."
    )


def test_sorts_are_inherited_and_overridden_in_place():
    class Reordered(BookSorting):
        def author(self):
            """By author's name alone."""

            return self.join(Book.author).order_by(Author.name)

        def pages(self):
            """By length."""

            return self.order_by(Book.pages)

    assert [spec.name for spec in Reordered.__sorts__] == [
        "title",
        "author",
        "publisher",
        "rating",
        "name",
        "pages",
    ]
    assert order_by(Reordered.statement({"sort": "author"})) == "author.name, book.id"


def test_a_sort_takes_no_value():
    class Valued(Sorting):
        def title(self, value: str):
            return self.order_by(Book.title)

    with pytest.raises(FilterDeclarationError, match="must take no parameters"):
        _ = Valued.__sorts__


@pytest.mark.parametrize("decorator", [options(metadata={}), skip_null])
def test_field_decorators_are_refused_on_a_sort(decorator):
    class Decorated(Sorting):
        @decorator
        def title(self):
            return self.order_by(Book.title)

    with pytest.raises(FilterDeclarationError, match="no schema field of its own"):
        _ = Decorated.__sorts__


def test_descending_is_refused_on_a_filter():
    class Directed(Filters):
        @descending
        def title(self, value: str):
            return self.where(Book.title == value)

    with pytest.raises(FilterDeclarationError, match="cannot be @descending"):
        _ = Directed.__filters__


@pytest.mark.parametrize("name", ["order_by", "join", "where", "unwrap"])
def test_a_sort_cannot_shadow_a_statement_method(name):
    def a_sort(self):
        return self

    Shadowing = type("Shadowing", (Sorting,), {name: a_sort})

    with pytest.raises(FilterDeclarationError, match=f"{name} cannot be a sort"):
        _ = Shadowing.__sorts__


@pytest.mark.parametrize("name", ["apply", "statement", "Schema"])
def test_a_sort_cannot_shadow_what_the_class_provides(name):
    def a_sort(self):
        return self

    Shadowing = type("Shadowing", (Sorting,), {name: a_sort})

    with pytest.raises(FilterDeclarationError, match="the sorting class itself provides"):
        _ = Shadowing.__sorts__


def test_the_order_style_is_checked():
    class Misspelled(BookSorting):
        __order_style__ = "prefixed"  # type: ignore[assignment]

    with pytest.raises(FilterDeclarationError, match=r"expected one of OrderStyle\.CODE"):
        Misspelled.apply(select(Book), {})


def test_the_order_style_value_is_accepted_as_a_plain_string():
    class Spelled(BookSorting):
        __order_style__ = "prefix"  # type: ignore[assignment]

    assert order_by(Spelled.statement({"sort": "-title"})) == "book.title DESC, book.id DESC"


def test_the_default_sort_must_be_a_sort():
    class Missing(BookSorting):
        __default_sort__ = "-rating"

    with pytest.raises(FilterDeclarationError, match="not one of its sorts"):
        Missing.apply(select(Book), {})


def test_the_sort_and_order_fields_must_differ():
    class Clashing(BookSorting):
        __sort_field__ = "order"

    with pytest.raises(FilterDeclarationError, match="same field"):
        Clashing.apply(select(Book), {})


def test_a_class_with_no_sorts_has_no_schema():
    with pytest.raises(FilterDeclarationError, match="declares no sorts"):
        _ = Sorting.Schema


# --- applying ---------------------------------------------------------------------------


def test_nothing_chosen_and_no_default_leaves_the_statement_alone():
    statement = select(Book).order_by(Book.pages)

    assert BookSorting.apply(statement, None) is statement
    assert BookSorting.apply(statement, {"sort": None, "order": "desc"}) is statement


def test_a_sort_applies_ascending_with_the_primary_key_as_tiebreaker():
    assert order_by(BookSorting.statement({"sort": "title"})) == "book.title, book.id"


def test_desc_reverses_every_key_and_the_tiebreaker():
    ordered = order_by(BookSorting.statement({"sort": "author", "order": "desc"}))

    assert ordered == "author.name DESC, book.released_on ASC, book.id DESC"


def test_nulls_stay_where_the_sort_put_them_whichever_way_it_runs():
    ascending = order_by(BookSorting.statement({"sort": "publisher"}))
    reversed_ = order_by(BookSorting.statement({"sort": "publisher", "order": "desc"}))

    assert ascending == "publisher.name NULLS LAST, book.id"
    assert reversed_ == "publisher.name DESC NULLS LAST, book.id DESC"


def test_a_descending_sort_runs_descending_unless_asked_otherwise():
    assert order_by(BookSorting.statement({"sort": "rating"})).endswith(
        "DESC NULLS LAST, book.id DESC"
    )
    assert order_by(BookSorting.statement({"sort": "rating", "order": "asc"})).endswith(
        "NULLS LAST, book.id"
    )


def test_the_default_sort_applies_when_none_is_chosen():
    class Defaulted(BookSorting):
        __default_sort__ = "rating"

    assert "DESC NULLS LAST" in order_by(Defaulted.statement({}))
    assert "DESC" not in order_by(Defaulted.statement({"order": "asc"}))


def test_the_callers_ordering_is_kept_after_the_sort():
    statement = select(Book).order_by(Book.pages.desc())

    assert order_by(BookSorting.apply(statement, {"sort": "title"})) == (
        "book.title, book.pages DESC, book.id"
    )


def test_the_tiebreaker_is_not_repeated_when_already_ordered_by():
    class ById(BookSorting):
        def newest_id(self):
            """By ID."""

            return self.order_by(Book.id.desc())

    assert order_by(ById.statement({"sort": "newest_id"})) == "book.id DESC"


def test_the_tiebreaker_is_configurable():
    class ByTitle(BookSorting):
        __tiebreaker__ = (Book.title, Book.id)

    class NoTiebreaker(BookSorting):
        __tiebreaker__ = None

    assert order_by(ByTitle.statement({"sort": "author"})) == (
        "author.name, book.released_on DESC, book.title, book.id"
    )
    assert order_by(NoTiebreaker.statement({"sort": "title"})) == "book.title"


def test_there_is_no_tiebreaker_without_a_model():
    class Anonymous(Sorting):
        def title(self):
            """By title."""

            return self.order_by(Book.title)

    assert order_by(Anonymous.apply(select(Book), {"sort": "title"})) == "book.title"


def test_joins_are_deduplicated_against_the_incoming_statement():
    statement = select(Book).join(Book.author).where(Author.country == "AR")

    assert sql(BookSorting.apply(statement, {"sort": "author"})).count("JOIN author") == 1


def test_self_is_a_statement_that_keeps_its_direction_through_chaining():
    seen = []

    class Chained(Sorting[Book]):
        __tiebreaker__ = None

        def title(self):
            """By title, twice over."""

            seen.append(self)
            return self.where(Book.id > 0).order_by(Book.title).order_by(Book.pages)

    ordered = order_by(Chained.statement({"sort": "title", "order": "desc"}))

    assert isinstance(seen[0], Statement)
    assert ordered == "book.title DESC, book.pages DESC"


def test_a_sort_returning_none_is_reported():
    class Forgetful(Sorting):
        def title(self):
            self.order_by(Book.title)

    with pytest.raises(TypeError, match="returned None"):
        Forgetful.apply(select(Book), {"sort": "title"})


def test_a_statement_that_cannot_be_ordered_is_reported():
    with pytest.raises(TypeError, match="can be ordered"):
        BookSorting.apply(exists(select(Book)), {"sort": "title"})  # type: ignore[arg-type]


def test_an_unknown_sort_is_reported():
    with pytest.raises(UnknownSortError, match="no sort named 'isbn'"):
        BookSorting.statement({"sort": "isbn"})


def test_an_unknown_field_is_reported():
    with pytest.raises(UnknownSortError, match="no field\\(s\\) named direction"):
        BookSorting.statement({"sort": "title", "direction": "desc"})


def test_a_bad_order_code_is_reported():
    with pytest.raises(InvalidOrderError, match="'asc' or 'desc'"):
        BookSorting.statement({"sort": "title", "order": "DESC"})


def test_statement_without_a_model_says_how_to_give_it_one():
    class Anonymous(Sorting):
        def title(self):
            return self.order_by(Book.title)

    with pytest.raises(FilterDeclarationError, match=r"Anonymous\(Sorting\[Book\]\)"):
        Anonymous.statement({"sort": "title"})


# --- order styles ------------------------------------------------------------------------


class RenamedSorting(BookSorting):
    __sort_field__ = "sort_on"
    __order_field__ = "direction"


class AscFlagSorting(BookSorting):
    __sort_field__ = "sort_by"
    __order_style__ = OrderStyle.ASC_FLAG


class DescFlagSorting(BookSorting):
    __order_style__ = OrderStyle.DESC_FLAG


class PrefixSorting(BookSorting):
    __order_style__ = OrderStyle.PREFIX
    __default_sort__ = "rating"


def test_both_fields_can_be_renamed():
    statement = RenamedSorting.statement({"sort_on": "title", "direction": "desc"})

    assert order_by(statement) == "book.title DESC, book.id DESC"

    with pytest.raises(UnknownSortError, match="it reads 'sort_on' and 'direction'"):
        RenamedSorting.statement({"sort": "title"})


@pytest.mark.parametrize(
    ("sorting", "values", "expected"),
    [
        (AscFlagSorting, {"sort_by": "title", "asc": True}, "book.title, book.id"),
        (AscFlagSorting, {"sort_by": "title", "asc": False}, "book.title DESC, book.id DESC"),
        (AscFlagSorting, {"sort_by": "title"}, "book.title, book.id"),
        (DescFlagSorting, {"sort": "title", "desc": True}, "book.title DESC, book.id DESC"),
        (DescFlagSorting, {"sort": "title", "desc": False}, "book.title, book.id"),
        (PrefixSorting, {"sort": "title"}, "book.title, book.id"),
        (PrefixSorting, {"sort": "-title"}, "book.title DESC, book.id DESC"),
    ],
)
def test_each_style_reads_its_own_direction(sorting, values, expected):
    assert order_by(sorting.statement(values)) == expected


def test_a_flag_style_names_the_order_field_after_itself():
    assert [field.name for field in dataclasses.fields(AscFlagSorting.Schema)] == [
        "sort_by",
        "asc",
    ]
    assert [field.name for field in dataclasses.fields(DescFlagSorting.Schema)] == [
        "sort",
        "desc",
    ]


def test_a_flag_style_takes_only_a_bool():
    with pytest.raises(InvalidOrderError, match="must be a bool"):
        AscFlagSorting.statement({"sort_by": "title", "asc": "0"})


def test_the_prefix_style_has_no_order_field():
    assert [field.name for field in dataclasses.fields(PrefixSorting.Schema)] == ["sort"]

    with pytest.raises(UnknownSortError, match="no field\\(s\\) named order"):
        PrefixSorting.statement({"sort": "title", "order": "desc"})


def test_the_prefix_style_applies_a_bare_name_ascending_even_if_the_sort_is_descending():
    # `-` is the only way to say descending, so a bare name has to mean ascending.
    assert "DESC" not in order_by(PrefixSorting.statement({"sort": "rating"}))
    # With nothing chosen, the default runs in its own direction.
    assert "DESC NULLS LAST" in order_by(PrefixSorting.statement({}))


# --- the dataclass schema ----------------------------------------------------------------


def test_the_schema_lists_the_sorts_as_choices():
    fields = {field.name: field for field in dataclasses.fields(BookSorting.Schema)}

    assert BookSorting.Schema.__name__ == "BookSortingSchema"
    assert BookSorting.Schema.__doc__ == "Orderings for the book catalogue."
    assert (
        fields["sort"].type
        == typing.Optional[  # noqa: UP045
            typing.Literal["title", "author", "publisher", "rating", "name"]
        ]
    )
    assert fields["sort"].default is None
    assert fields["order"].type == typing.Optional[typing.Literal["asc", "desc"]]  # noqa: UP045
    assert fields["order"].default is None


def test_the_sort_field_is_described_by_the_docstrings():
    description = dataclasses.fields(BookSorting.Schema)[0].metadata["description"]

    assert description == (
        "How to order the results.\n"
        "\n"
        "- `title`: By title.\n"
        "- `author`: By author's name, then the newest book first.\n"
        "- `publisher`: By publisher's name, books without one last.\n"
        "- `rating`: By average review score. Descending unless stated otherwise.\n"
        "- `name`: By title, under its old name. Deprecated: The 'name' sort is "
        "deprecated. Use 'title' instead."
    )


def test_a_default_sort_makes_the_field_required_with_a_default():
    sort = dataclasses.fields(PrefixSorting.Schema)[0]

    assert sort.default == "-rating"
    assert typing.get_args(sort.type) == (
        "title",
        "-title",
        "author",
        "-author",
        "publisher",
        "-publisher",
        "rating",
        "-rating",
        "name",
        "-name",
    )


def test_apply_takes_a_schema_instance():
    values = RenamedSorting.Schema(sort_on="author", direction="desc")

    assert order_by(RenamedSorting.apply(select(Book), values)).startswith("author.name DESC")


def test_an_explicit_asc_is_reversed_too_and_a_bare_sort_is_listed_by_name():
    class Explicit(Sorting[Book]):
        __tiebreaker__ = None

        def title(self):
            return self.order_by(Book.title.asc())

    assert order_by(Explicit.statement({"sort": "title", "order": "desc"})) == "book.title DESC"
    assert dataclasses.fields(Explicit.Schema)[0].metadata["description"] == (
        "How to order the results.\n\n- `title`"
    )
