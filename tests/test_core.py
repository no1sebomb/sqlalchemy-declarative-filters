"""The dataclass backend, filter collection, and join planning."""

import dataclasses
import datetime
import decimal

import pytest
from sqlalchemy import select

from sqlalchemy_declarative_filters import (
    Filters,
    FilterDeclarationError,
    JoinConflictWarning,
    Statement,
    UnknownFilterError,
    options,
    skip_null,
)

from .conftest import Author, Availability, Book, Genre, Publisher, Review, Tag, sql


class BookFilters(Filters):
    """Parameters for filtering the book catalogue."""

    # --- scalar filters, no default: omitting one is how you skip it ----------------

    def ids(self, value: list[int]):
        """Only books with one of these IDs."""

        return self.where(Book.id.in_(value))

    @options(metadata={"example": "tomb"})
    def title(self, value: str):
        """Books whose title contains this."""

        return self.where(Book.title.ilike(f"%{value}%"))

    def genre(self, value: Genre):
        """Books of this genre."""

        return self.where(Book.genre == value)

    def genres(self, value: list[Genre]):
        """Books with any of these genres."""

        return self.where(Book.genre.in_(value))

    def published_after(self, value: int):
        """Books first published after this year."""

        return self.where(Book.published_in > value)

    def min_pages(self, value: int):
        """Books at least this long."""

        return self.where(Book.pages >= value)

    def max_price(self, value: decimal.Decimal):
        """Books at most this expensive."""

        return self.where(Book.price <= value)

    def released_after(self, value: datetime.date):
        """Books released after this date."""

        return self.where(Book.released_on > value)

    def has_publisher(self, value: bool):
        """Books that do, or do not, have a publisher."""

        return self.where(Book.publisher_id.is_not(None) if value else Book.publisher_id.is_(None))

    # --- a default that holds unless the caller switches it off --------------------

    @skip_null
    def availability(self, value: Availability = Availability.IN_PRINT):
        """Books with this availability. Pass null for any."""

        return self.where(Book.availability == value)

    # --- filters that reach another table through a join ---------------------------

    def author_name(self, value: str):
        """Books whose author's name contains this."""

        return self.join(Book.author).where(Author.name.ilike(f"%{value}%"))

    def author_country(self, value: str):
        """Books by an author from this country."""

        return self.join(Book.author).where(Author.country == value)

    def publisher_name(self, value: str):
        """Books from this publisher."""

        return self.outerjoin(Book.publisher).where(Publisher.name == value)

    def tag(self, value: str):
        """Books carrying this tag."""

        return self.join(Book.tags).where(Tag.name == value)

    # --- filters that reach another table without one ------------------------------

    def min_rating(self, value: int):
        """Books with at least one review scoring this or better."""

        return self.where(Book.reviews.any(Review.rating >= value))

    def author_born_after(self, value: int):
        """Books by an author born after this year."""

        return self.where(Book.author.has(Author.born_in > value))


ALL_FILTERS = [
    "ids",
    "title",
    "genre",
    "genres",
    "published_after",
    "min_pages",
    "max_price",
    "released_after",
    "has_publisher",
    "availability",
    "author_name",
    "author_country",
    "publisher_name",
    "tag",
    "min_rating",
    "author_born_after",
]


# --- the generated schema ----------------------------------------------------------


def test_schema_is_a_dataclass():
    schema = BookFilters.Schema

    assert dataclasses.is_dataclass(schema)
    assert schema.__name__ == "BookFiltersSchema"
    assert schema.__doc__ == "Parameters for filtering the book catalogue."
    assert [f.name for f in dataclasses.fields(schema)] == ALL_FILTERS


def test_model_and_dataclass_are_the_same_object_as_schema():
    assert BookFilters.Model is BookFilters.Schema
    assert BookFilters.Dataclass is BookFilters.Schema


@pytest.mark.parametrize(
    ("name", "annotation"),
    [
        ("ids", list[int] | None),
        ("title", str | None),
        ("genre", Genre | None),
        ("genres", list[Genre] | None),
        ("published_after", int | None),
        ("max_price", decimal.Decimal | None),
        ("released_after", datetime.date | None),
        ("has_publisher", bool | None),
        # Has a default and opted into skip_null, so null switches the default off.
        ("availability", Availability | None),
    ],
)
def test_annotations_carry_through_to_the_schema(name, annotation):
    fields = {f.name: f for f in dataclasses.fields(BookFilters.Schema)}

    assert fields[name].type == annotation


def test_a_declared_default_becomes_the_field_default():
    fields = {f.name: f for f in dataclasses.fields(BookFilters.Schema)}

    assert fields["availability"].default is Availability.IN_PRINT
    assert fields["title"].default is None


def test_a_defaulted_filter_without_skip_null_is_not_optional():
    class Defaulted(Filters):
        def min_pages(self, value: int = 100):
            """Always applied, with 100 unless told otherwise."""

            return self.where(Book.pages >= value)

    field = dataclasses.fields(Defaulted.Schema)[0]

    assert field.type is int
    assert field.default == 100


def test_docstring_becomes_the_field_description():
    fields = {f.name: f for f in dataclasses.fields(BookFilters.Schema)}

    assert fields["title"].metadata["description"] == "Books whose title contains this."
    assert fields["title"].metadata["example"] == "tomb"


# --- applying filters --------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"ids": [1, 2, 3]}, "book.id IN"),
        ({"title": "tomb"}, "lower(book.title) LIKE lower"),
        ({"genre": Genre.POETRY}, "book.genre = "),
        ({"genres": [Genre.POETRY, Genre.HISTORY]}, "book.genre IN"),
        ({"published_after": 1980}, "book.published_in > "),
        ({"min_pages": 300}, "book.pages >= "),
        ({"max_price": decimal.Decimal("9.99")}, "book.price <= "),
        ({"released_after": datetime.date(2020, 1, 1)}, "book.released_on > "),
        ({"has_publisher": True}, "book.publisher_id IS NOT NULL"),
        ({"has_publisher": False}, "book.publisher_id IS NULL"),
        ({"min_rating": 4}, "EXISTS (SELECT 1 FROM review"),
        ({"author_born_after": 1900}, "EXISTS (SELECT 1 FROM author"),
    ],
)
def test_each_filter_shape_compiles(values, expected):
    assert expected in sql(BookFilters.apply(select(Book), values))


def test_apply_with_a_schema_instance():
    values = BookFilters.Schema(ids=[1, 2], title="tomb")

    assert "book.id IN" in sql(BookFilters.apply(select(Book), values))


def test_declared_default_applies_when_the_caller_omits_it():
    # The regression this library exists to avoid: exclude_unset dropping the default.
    assert "book.availability = " in sql(BookFilters.apply(select(Book), {}))


def test_skip_null_turns_a_defaulted_filter_off():
    assert "WHERE" not in sql(BookFilters.apply(select(Book), {"availability": None}))


def test_none_values_are_skipped():
    values = {"title": None, "genre": None, "availability": None}

    assert sql(BookFilters.apply(select(Book), values)) == sql(select(Book))


def test_apply_accepts_none():
    assert "book.availability = " in sql(BookFilters.apply(select(Book), None))


def test_filters_combine():
    compiled = sql(BookFilters.apply(select(Book), {"title": "tomb", "min_pages": 300}))

    assert "lower(book.title) LIKE lower" in compiled
    assert "book.pages >= " in compiled
    assert "book.availability = " in compiled


def test_unknown_filter_is_rejected():
    with pytest.raises(UnknownFilterError, match="no filter"):
        BookFilters.apply(select(Book), {"isbn": "978-0"})


def test_filters_apply_in_declaration_order_not_input_order():
    forwards = BookFilters.apply(select(Book), {"ids": [1], "title": "a"})
    backwards = BookFilters.apply(select(Book), {"title": "a", "ids": [1]})

    assert sql(forwards) == sql(backwards)


# --- the dataclass backend's own entry point ---------------------------------------


def test_null_strings_coerce_through_from_mapping():
    values = BookFilters.Schema.from_mapping({"availability": "null", "title": "tomb"})

    assert values.availability is None
    assert values.title == "tomb"


def test_from_mapping_rejects_unknown_names():
    with pytest.raises(TypeError, match="no filter"):
        BookFilters.Schema.from_mapping({"isbn": "978-0"})


# --- declaring filters -------------------------------------------------------------


def test_inheritance_extends_the_schema():
    class RareBookFilters(BookFilters):
        def first_edition(self, value: bool):
            """Only first editions."""

            return self.where(Book.published_in == Book.published_in) if value else self

    names = [f.name for f in dataclasses.fields(RareBookFilters.Schema)]

    assert names == [*ALL_FILTERS, "first_edition"]
    # The parent's own schema is untouched.
    assert [f.name for f in dataclasses.fields(BookFilters.Schema)] == ALL_FILTERS


def test_a_subclass_can_override_a_filter_in_place():
    class ExactTitle(BookFilters):
        def title(self, value: str):
            """Books with exactly this title."""

            return self.where(Book.title == value)

    assert [f.name for f in dataclasses.fields(ExactTitle.Schema)] == ALL_FILTERS
    assert "lower(book.title)" not in sql(ExactTitle.apply(select(Book), {"title": "x"}))


def test_private_methods_are_not_filters():
    class WithHelper(Filters):
        def _normalise(self, value: str) -> str:
            return value.strip()

        def title(self, value: str):
            """Books whose title contains this."""

            return self.where(Book.title.ilike(f"%{value}%"))

    assert [f.name for f in dataclasses.fields(WithHelper.Schema)] == ["title"]


def test_a_filter_must_annotate_its_value():
    class Bad(Filters):
        def oops(self, value):
            return self

    with pytest.raises(FilterDeclarationError, match="must annotate"):
        _ = Bad.Schema


def test_a_filter_must_take_exactly_one_value():
    class Bad(Filters):
        def oops(self, first: int, second: int):
            return self

    with pytest.raises(FilterDeclarationError, match="exactly one parameter"):
        _ = Bad.Schema


# --- joins -------------------------------------------------------------------------


def test_a_join_brings_in_the_other_table():
    compiled = sql(BookFilters.apply(select(Book), {"author_name": "borges"}))

    assert "JOIN author" in compiled
    assert "lower(author.name) LIKE lower" in compiled


def test_two_filters_sharing_a_join_join_once():
    values = {"author_name": "borges", "author_country": "AR"}

    assert sql(BookFilters.apply(select(Book), values)).count("JOIN author") == 1


def test_a_join_the_caller_already_made_is_not_repeated():
    statement = BookFilters.apply(select(Book).join(Author), {"author_name": "borges"})

    assert sql(statement).count("JOIN author") == 1


def test_a_join_the_caller_made_via_a_relationship_is_not_repeated():
    statement = BookFilters.apply(select(Book).join(Book.author), {"author_name": "borges"})

    assert sql(statement).count("JOIN author") == 1


def test_a_join_the_caller_made_via_the_table_is_not_repeated():
    statement = BookFilters.apply(select(Book).join(Author.__table__), {"author_name": "borges"})

    assert sql(statement).count("JOIN author") == 1


def test_joins_of_inactive_filters_are_not_applied():
    assert "JOIN" not in sql(BookFilters.apply(select(Book), {"title": "tomb"}))


def test_outer_joins_are_honoured():
    compiled = sql(BookFilters.apply(select(Book), {"publisher_name": "NYRB"}))

    assert "LEFT OUTER JOIN publisher" in compiled


def test_a_many_to_many_join_brings_in_both_tables():
    compiled = sql(BookFilters.apply(select(Book), {"tag": "translated"}))

    assert "JOIN book_tag" in compiled
    assert "JOIN tag" in compiled


def test_unrelated_joins_are_all_applied():
    values = {"author_name": "borges", "publisher_name": "NYRB", "tag": "translated"}
    compiled = sql(BookFilters.apply(select(Book), values))

    assert compiled.count("JOIN author") == 1
    assert compiled.count("LEFT OUTER JOIN publisher") == 1
    assert compiled.count("JOIN tag") == 1


def test_conflicting_join_options_warn_and_keep_the_first():
    class Conflicting(Filters):
        def author_country(self, value: str):
            """Inner join."""

            return self.join(Author).where(Author.country == value)

        def author_name(self, value: str):
            """Outer join for the same table."""

            return self.outerjoin(Author).where(Author.name == value)

    with pytest.warns(JoinConflictWarning, match="Conflicting joins"):
        statement = Conflicting.apply(select(Book), {"author_country": "AR", "author_name": "b"})

    compiled = sql(statement)

    assert compiled.count("JOIN author") == 1
    assert "LEFT OUTER JOIN" not in compiled


def test_several_joins_in_one_filter_apply_in_call_order():
    class Chained(Filters):
        def author_of_tagged(self, value: str):
            """Needs both tables."""

            return self.join(Book.tags).join(Book.author).where(Author.name == value)

    compiled = sql(Chained.apply(select(Book), {"author_of_tagged": "borges"}))

    assert compiled.index("JOIN book_tag") < compiled.index("JOIN author")


def test_a_join_can_be_conditional():
    class Conditional(Filters):
        def author_or_title(self, value: str):
            """Reaches the author table only when the value looks like an author."""

            if value.startswith("by:"):
                return self.join(Book.author).where(Author.name == value[3:])

            return self.where(Book.title == value)

    assert "JOIN author" in sql(Conditional.apply(select(Book), {"author_or_title": "by:borges"}))
    assert "JOIN" not in sql(Conditional.apply(select(Book), {"author_or_title": "tomb"}))


def test_a_filter_can_unwrap_and_still_be_deduplicated():
    class Unwrapping(Filters):
        def author_name(self, value: str):
            """Drops to the raw statement, which the next filter must not duplicate."""

            return self.join(Book.author).unwrap().where(Author.name == value)

        def author_country(self, value: str):
            """Books by an author from this country."""

            return self.join(Book.author).where(Author.country == value)

    values = {"author_name": "borges", "author_country": "AR"}

    assert sql(Unwrapping.apply(select(Book), values)).count("JOIN author") == 1


def test_apply_returns_a_plain_sqlalchemy_statement():
    from sqlalchemy.sql.selectable import Select

    assert isinstance(BookFilters.apply(select(Book), {"author_name": "borges"}), Select)


def test_statement_methods_other_than_join_are_forwarded():
    class Ordered(Filters):
        def newest_first(self, value: bool):
            """Not really a filter, but it proves order_by chains."""

            return self.order_by(Book.published_in.desc()) if value else self

    assert "ORDER BY book.published_in DESC" in sql(
        Ordered.apply(select(Book), {"newest_first": True})
    )


def test_a_filter_that_returns_nothing_says_so():
    class Forgetful(Filters):
        def title(self, value: str):
            """Forgets to return the statement."""

            self.where(Book.title == value)

    with pytest.raises(TypeError, match="returned None"):
        Forgetful.apply(select(Book), {"title": "tomb"})


def test_relationship_predicates_need_no_join_at_all():
    compiled = sql(BookFilters.apply(select(Book), {"min_rating": 4, "author_born_after": 1900}))

    assert "JOIN" not in compiled
    assert compiled.count("EXISTS") == 2


# --- backends ----------------------------------------------------------------------


def test_a_missing_extra_reports_how_to_install_it(monkeypatch):
    from sqlalchemy_declarative_filters import BackendNotAvailableError
    from sqlalchemy_declarative_filters._backends import _BACKENDS, _LOADED

    monkeypatch.setitem(_BACKENDS, "pydantic", (".not_installed", "X", "pydantic"))
    monkeypatch.delitem(_LOADED, "pydantic", raising=False)

    with pytest.raises(BackendNotAvailableError, match=r"\[pydantic\]"):
        _ = BookFilters.Pydantic


def test_an_unknown_backend_name_is_rejected():
    class Odd(Filters):
        __backend__ = "sqlalchemy"

        def ids(self, value: list[int]):
            """Only books with one of these IDs."""

            return self.where(Book.id.in_(value))

    with pytest.raises(ValueError, match="Unknown schema backend"):
        _ = Odd.Schema


def test_every_namespace_exports_the_same_statement():
    from sqlalchemy_declarative_filters import marshmallow, pydantic

    assert pydantic.Statement is Statement
    assert marshmallow.Statement is Statement


def test_self_inside_a_filter_is_that_statement():
    seen = {}

    class Introspecting(Filters):
        def title(self, value: str):
            """Looks at what it was handed."""

            seen["self"] = self

            return self.where(Book.title == value)

    Introspecting.apply(select(Book), {"title": "tomb"})

    assert isinstance(seen["self"], Statement)


def test_methods_that_leave_the_statement_behind_return_it_unwrapped():
    from sqlalchemy.sql.selectable import Subquery

    seen = {}

    class Inspecting(Filters):
        def title(self, value: str):
            """Records what the wrapper hands back."""

            seen["subquery"] = self.where(Book.title == value).subquery()

            return self.where(Book.title == value)

    Inspecting.apply(select(Book), {"title": "tomb"})

    assert isinstance(seen["subquery"], Subquery)


def test_unwrap_is_the_escape_hatch_for_type_checked_arguments():
    class Correlated(Filters):
        def title(self, value: str):
            """`in_` inspects its argument's type, so the wrapper has to come off."""

            inner = self.where(Book.title == value).with_only_columns(Book.id).unwrap()

            return self.where(Book.id.in_(inner))

    assert "book.id IN (SELECT book.id" in sql(Correlated.apply(select(Book), {"title": "t"}))


@pytest.mark.parametrize("name", ["where", "having", "join", "outerjoin", "unwrap"])
def test_a_filter_cannot_shadow_a_statement_method(name):
    def a_filter(self, value: str):
        """Intended as a filter."""

        return self.where(Book.title == value)

    Shadowing = type("Shadowing", (Filters,), {name: a_filter})

    with pytest.raises(FilterDeclarationError, match=f"{name} cannot be a filter"):
        _ = Shadowing.__filters__


@pytest.mark.parametrize("name", ["order_by", "distinct", "limit", "offset", "subquery"])
def test_other_statement_method_names_are_still_available(name):
    def a_filter(self, value: str):
        """A filter that happens to share a name with a statement method."""

        return self.where(Book.title == value)

    Named = type("Named", (Filters,), {name: a_filter})

    assert [spec.name for spec in Named.__filters__] == [name]
    assert "book.title = " in sql(Named.apply(select(Book), {name: "tomb"}))


def test_a_shadowing_filter_can_keep_its_parameter_name_by_aliasing():
    from sqlalchemy_declarative_filters.pydantic import Filters as PydanticFilters
    from sqlalchemy_declarative_filters.pydantic import options as pydantic_options

    class Aliased(PydanticFilters):
        """The method is renamed; the query parameter is not."""

        @pydantic_options(alias="join", validation_alias="join")
        def join_clause(self, value: str):
            """Books whose title contains this."""

            return self.where(Book.title.ilike(f"%{value}%"))

    values = Aliased.Schema(join="tomb")

    assert "lower(book.title) LIKE lower" in sql(Aliased.apply(select(Book), values))
