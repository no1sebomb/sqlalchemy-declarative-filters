# sqlalchemy-declarative-filters

[![CI](https://github.com/no1sebomb/sqlalchemy-declarative-filters/actions/workflows/ci.yml/badge.svg)](https://github.com/no1sebomb/sqlalchemy-declarative-filters/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sqlalchemy-declarative-filters.svg)](https://pypi.org/project/sqlalchemy-declarative-filters/)
[![Python](https://img.shields.io/pypi/pyversions/sqlalchemy-declarative-filters.svg)](https://pypi.org/project/sqlalchemy-declarative-filters/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-d71f00.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)

Declare a filter set once, as a class. Get a validated schema and a SQLAlchemy
statement builder out of it.

> **Status: pre-release.** The API is not stable yet.

```python
from sqlalchemy_declarative_filters import Filters, options, skip_null


class BookFilters(Filters):
    """Parameters for filtering the book catalogue."""

    def ids(self, value: list[int]):
        """Only books with one of these IDs."""
        return self.where(Book.id.in_(value))

    @options(metadata={"example": "tomb"})
    def title(self, value: str):
        """Books whose title contains this."""
        return self.where(Book.title.ilike(f"%{value}%"))

    def genres(self, value: list[Genre]):
        """Books of any of these genres."""
        return self.where(Book.genre.in_(value))

    def author_name(self, value: str):
        """Books whose author's name contains this."""
        return self.join(Book.author).where(Author.name.ilike(f"%{value}%"))

    @skip_null
    def availability(self, value: Availability = Availability.IN_PRINT):
        """Books with this availability. Pass null for any."""
        return self.where(Book.availability == value)
```

```python
statement = BookFilters.apply(select(Book), {"title": "tomb", "genres": [Genre.POETRY]})
# SELECT ... FROM book
# WHERE lower(book.title) LIKE lower(:t) AND book.genre IN (...)
#   AND book.availability = :a          <- the declared default, applied
```

`BookFilters.Schema` is a generated schema class -- a dataclass by default, a Pydantic
model or a Marshmallow schema if you ask for one. It is built from the same
declarations: the annotation becomes the field's type, the default becomes its
default, the docstring becomes its description.

## Install

```console
pip install sqlalchemy-declarative-filters                 # dataclass schemas
pip install sqlalchemy-declarative-filters[pydantic]       # Pydantic models
pip install sqlalchemy-declarative-filters[marshmallow]    # Marshmallow schemas
```

SQLAlchemy 2.0 is the only hard dependency. Python 3.10+.

## Writing filters

Every public method in the class body is a filter. It takes the statement being built
as `self` and the filter's value as its only other parameter, and returns the narrowed
statement. Methods are never bound -- `apply` calls them with the statement in the
`self` position -- so `self.where(...)` is SQLAlchemy's own `where`.

| declaration | effect |
| --- | --- |
| the value's annotation | the schema field's type |
| the value's default | the schema field's default, always applied |
| the docstring | the schema field's description |
| a leading `_` | not a filter |

Five names are unavailable: `where`, `having`, `join`, `outerjoin` and `unwrap`. Those
are the methods a filter body calls on `self`, so a type checker would read a filter
of that name as an override of the method rather than as a filter. Declaring one
raises `FilterDeclarationError` -- it is never silently ignored. Everything else a
statement offers, `order_by` and `distinct` and the rest, is still a usable filter
name. If the *incoming parameter* has to be called `where`, rename the method and
alias the field: `@options(alias="where")` on Pydantic, `data_key="where"` on
Marshmallow.

A filter with **no default** is skipped when its value is `None`; omitting it is how
you say "do not filter on this". A filter **with** a default is always applied, even
when the caller does not mention it. To let a caller switch a default off, add
`@skip_null`: the field then accepts `None`, and the strings `""`, `"null"` and
`"none"` so a query string can say it too.

Filters are inherited, so a project usually defines one base and extends it. A
subclass redefining a name overrides that filter in place.

### What a filter can be

Anything you can write as a `where` clause. The annotation is the only thing the
schema needs, so the whole range works:

```python
def ids(self, value: list[int]):  # a list of primary keys
    """Only books with one of these IDs."""
    return self.where(Book.id.in_(value))


def title(self, value: str):  # substring match
    """Books whose title contains this."""
    return self.where(Book.title.ilike(f"%{value}%"))


def genre(self, value: Genre):  # an enum
    """Books of this genre."""
    return self.where(Book.genre == value)


def genres(self, value: list[Genre]):  # a list of enums
    """Books of any of these genres."""
    return self.where(Book.genre.in_(value))


def published_after(self, value: int):  # a number
    """Books first published after this year."""
    return self.where(Book.published_in > value)


def max_price(self, value: decimal.Decimal):  # a decimal
    """Books at most this expensive."""
    return self.where(Book.price <= value)


def released_after(self, value: datetime.date):  # a date
    """Books released after this date."""
    return self.where(Book.released_on > value)


def has_publisher(self, value: bool):  # a flag, either way round
    """Books that do, or do not, have a publisher."""
    return self.where(Book.publisher_id.is_not(None) if value else Book.publisher_id.is_(None))


@skip_null
def availability(self, value: Availability = Availability.IN_PRINT):
    """Applied with IN_PRINT unless the caller says otherwise; null switches it off."""
    return self.where(Book.availability == value)


def author_name(self, value: str):  # reaches another table
    """Books whose author's name contains this."""
    return self.join(Book.author).where(Author.name.ilike(f"%{value}%"))


def min_rating(self, value: int):  # reaches one without a join
    """Books with at least one review scoring this or better."""
    return self.where(Book.reviews.any(Review.rating >= value))
```

## Picking a backend

The three namespaces export the same names, so a project changes backend by editing
one import:

```python
from sqlalchemy_declarative_filters import Filters, options, skip_null  # dataclass
from sqlalchemy_declarative_filters.pydantic import Filters, options, skip_null  # Pydantic
from sqlalchemy_declarative_filters.marshmallow import Filters, options, skip_null  # Marshmallow
```

Do it once in your own base module and the filter classes themselves never mention a
backend:

```python
# db/filters.py
from sqlalchemy_declarative_filters.pydantic import Filters, Statement, options, skip_null

__all__ = ("Filters", "Statement", "options", "skip_null")
```

```python
# catalogue/filters.py
from db.filters import Filters, options, skip_null


class BookFilters(Filters): ...
```

`Filters`, `PydanticFilters` and `MarshmallowFilters` name the same classes; use the
long form when two backends meet in one module.

|  | dataclass | Pydantic | Marshmallow |
| --- | --- | --- | --- |
| dependency | none | `[pydantic]` | `[marshmallow]` |
| `Schema` is | a `@dataclass` | a `BaseModel` subclass | a `Schema` subclass |
| validates | no | yes | yes |
| `@options` takes | `dataclasses.field` keywords | `pydantic.Field` keywords | `marshmallow.fields.Field` keywords |
| feed `apply` | the instance | the instance | `Schema().load(params)`, which is a dict |

The dataclass backend is a typed container, not a validator. Nothing checks that the
values match their annotations. It exists so the library installs with no dependencies
and so `apply(statement, some_dict)` needs nothing at all; reach for Pydantic or
Marshmallow when the values come from outside your own code.

Any class can reach any backend -- `BookFilters.Dataclass`, `.Pydantic`,
`.Marshmallow` -- each built lazily and cached. `Model` is an alias of `Schema`.

### `@options` is backend-specific

Keywords go to the active backend's own field constructor, untranslated, and each
namespace ships a type stub pinning them to it. So you get real completion:

```python
@options(min_length=3, examples=["tomb"])       # .pydantic     -> pydantic.Field
@options(validate=validate.Length(min=3))       # .marshmallow  -> fields.Field
@options(metadata={"example": "tomb"})          # dataclass     -> dataclasses.field
```

Mixing them is an error you get at schema-build time, naming the backend, not a silent
misconfiguration. Import `options` from the same place as `Filters` and this cannot
happen.

## With FastAPI

```python
from catalogue.filters import BookFilters  # a .pydantic Filters subclass


@router.get("/books")
async def get_books(
    filters: Annotated[BookFilters.Schema, Query()],
    db_session: AsyncSession = Depends(get_session),
):
    return await db_session.scalars(BookFilters.apply(select(Book), filters))
```

The generated model carries the descriptions and constraints, so the OpenAPI document
documents itself.

> Do not reach for `model_dump(exclude_unset=True)` on the way in. FastAPI leaves an
> unprovided query parameter unset, so a filter declaring `availability: Availability =
> Availability.IN_PRINT` would be dropped before it was ever applied -- the default
> silently would not hold. `apply` takes the model directly and applies declared
> defaults.

## Joins

SQLAlchemy does not deduplicate joins. `select(Book).join(Author).join(Author)`
compiles to `FROM book JOIN author ON ... JOIN author ON ...`, which most databases
reject and the rest answer wrongly. So two filters that both need the same join cannot
each call `.join()` on the statement, and neither can a filter whose join the caller
already added.

`self.join()` can, because `self` is not the raw statement. It is a `Statement`: every
method forwards to the statement untouched, except `join`, which deduplicates first.
All the filters in one `apply` share the same record of what has been joined, seeded
from the statement that came in.

```python
class BookFilters(Filters):
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
```

```python
BookFilters.apply(select(Book), {"author_name": "borges", "author_country": "AR"})
# ... FROM book JOIN author ON ...              <- once
BookFilters.apply(select(Book).join(Author), {"author_name": "borges"})
# ... FROM book JOIN author ON ...              <- still once
```

Because the join is a statement, not a declaration, it can be conditional:

```python
def written_or_titled(self, value: str):
    """Books by this author, or with this in the title."""
    if value.startswith("by:"):
        return self.join(Book.author).where(Author.name == value[3:])
    return self.where(Book.title.ilike(f"%{value}%"))
```

A many-to-many relationship brings in its association table on its own. Targets are
matched by the selectable they resolve to, so `Book.author`, `Author` and
`Author.__table__` are one target, while two `aliased(Author)` constructs are two.
When two filters ask for the same target with different options, the first wins and a
`JoinConflictWarning` says so.

### Prefer not to join

For pure filtering, a correlated predicate beats a join. It cannot collide with another
filter's join, and -- unlike a join to a collection -- it does not multiply result rows
and inflate the count behind your pagination:

```python
def author_born_after(self, value: int):
    """Books by an author born after this year."""
    return self.where(Book.author.has(Author.born_in > value))


def min_rating(self, value: int):
    """Books with at least one review scoring this or better."""
    return self.where(Book.reviews.any(Review.rating >= value))
```

Keep `join` for when you need the joined table for something other than the predicate,
such as ordering by one of its columns.

`Exists` has no `.join()`, so a filter set applied to one must not call `self.join()`.

### Getting the raw statement back

`apply` returns a plain SQLAlchemy statement, so callers never see the wrapper. Inside
a filter, the few places SQLAlchemy inspects an argument's type rather than calling a
method on it -- `Column.in_()`, `union()` -- need `self.unwrap()`:

```python
def cheapest(self, value: int):
    """Books among the N cheapest."""
    inner = self.with_only_columns(Book.id).order_by(Book.price).limit(value).unwrap()
    return self.where(Book.id.in_(inner))
```

Joins stay deduplicated afterwards: whatever a filter returns is re-wrapped with the
same join record before the next filter runs.

## Reference

```python
BookFilters.Schema  # the generated schema, in this class's backend
BookFilters.Model  # alias of Schema
BookFilters.Dataclass  # the same filters as a dataclass
BookFilters.Pydantic  # ... as a Pydantic model
BookFilters.Marshmallow  # ... as a Marshmallow schema
BookFilters.apply(statement, values=None)  # values: a mapping, a schema instance, or None
BookFilters.__filters__  # the collected FilterSpec objects
```

Class attributes you can set on a filters class:

```python
__backend__  # "dataclass" | "pydantic" | "marshmallow"; normally set by the base
__null_strings__  # strings that mean null on a @skip_null filter
__schema_name__  # overrides the generated schema's class name
```

`Statement` is what `self` is and what a filter returns, so under a strict type checker
that is the return annotation:

```python
def title(self, value: str) -> Statement:
    """Books whose title contains this."""
    return self.where(Book.title.ilike(f"%{value}%"))
```

Errors all derive from `FilterError`: `FilterDeclarationError` for a filter that cannot
be turned into a field, `UnknownFilterError` for a value with no matching filter,
`BackendNotAvailableError` when an extra is missing.

## Licence

MIT.
