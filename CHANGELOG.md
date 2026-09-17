# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `Sorting`, the counterpart of `Filters` for ordering. Each public method is a sort:
  it takes only `self`, the same join-deduplicating `Statement` a filter gets, and
  writes its ascending order with `self.order_by(...)`. When the caller asks for
  descending, every key is reversed on the way through, `NULLS FIRST/LAST` kept.
  `@descending` makes a sort run descending by default. The generated schema offers the
  sorts as a `Literal`, described by their docstrings.
- How the choice arrives is configurable per class: `__sort_field__` and
  `__order_field__` name the fields, and `__order_style__` spells the direction as a
  code (`order=desc`), a flag (`asc=0` or `desc=1`) or a prefix (`sort=-title`): one of
  the new `OrderStyle` members, `CODE`, `ASC_FLAG`, `DESC_FLAG` and `PREFIX`.
  `__default_sort__` applies when the caller picks nothing.
- A sort is followed by the statement's existing ordering and then by `__tiebreaker__`,
  the model's primary key by default, so that paginated results never repeat or skip
  rows.
- `UnknownSortError` and `InvalidOrderError`.

### Changed

- `FiltersMeta` now derives from `SchemaMeta`, which it shares with `SortingMeta`. The
  public surface of `FiltersMeta` is unchanged.

## [0.2.0] - 2026-09-14

### Added

- `Filters` takes the model it filters as a type parameter:
  `class BookFilters(Filters[Book])`. A type checker then holds `apply` to it, so
  passing a statement over another table is an error. Unparameterised classes are
  checked exactly as before. ([#3])
- `statement(values)` builds `select(model)` with the filters applied, and
  `condition(values)` compiles them to one `WHERE` clause for statements you build
  yourself. Both read the model from the type parameter, or from an explicit
  `__model__`. Filters that add a join or a `HAVING` cannot be a bare clause and raise
  the new `FilterConditionError`. ([#4])
- `@deprecated` marks a filter as on its way out. The filter keeps working; the
  generated schema field is flagged deprecated -- `"deprecated": true` in the OpenAPI
  document -- and the reason, or the filter to use instead, is appended to the field's
  description. Spelled `@deprecated`, `@deprecated("why")` or
  `@deprecated(alternative="other_filter")`. ([#2])
- `@skip_null` on a filter that declares no default now warns with
  `RedundantSkipNullWarning`: such a filter is already skipped when its value is
  `None`, so the decorator changes nothing. ([#1])

### Changed

- A filter may no longer be named after something the filters class itself provides
  (`apply`, `statement`, `condition`, `build_schema`, `Schema` and the rest); such a
  filter shadowed the method instead of being applied. It now raises
  `FilterDeclarationError`, the way the reserved statement methods already did.
- `typing-extensions>=4.6` is now a declared dependency. The stubs give the model
  type parameter a PEP 696 default, so a plain `Filters` stays usable under
  `disallow_any_generics`. SQLAlchemy already required it, so nothing new is
  installed.
- A declaration error reaching `Schema` is no longer re-raised as a backend error:
  `FilterDeclarationError` is a `TypeError`, so it was being caught by the handler
  that explains `@options` mismatches.

[#1]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/issues/1
[#2]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/issues/2
[#3]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/issues/3
[#4]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/issues/4

## [0.1.0] - 2026-09-07

### Added

- `Filters` base class: every public method in the body becomes a filter, with the
  value parameter's annotation, default and docstring driving the generated schema.
- Three schema backends behind identical namespaces, so switching is one import line:
  `sqlalchemy_declarative_filters` (dataclass, no dependencies),
  `.pydantic` and `.marshmallow` (the `pydantic` and `marshmallow` extras).
- `Schema` / `Model` on a filters class, plus `Dataclass`, `Pydantic` and
  `Marshmallow` for reaching a second backend from the same class. All built lazily
  and cached per class.
- `self` inside a filter is a `Statement`, which forwards everything to the SQLAlchemy
  statement untouched except `join`, which is idempotent. Every filter in one `apply`
  shares the same record of what has been joined, seeded from the incoming statement,
  so a target is joined at most once however many filters ask for it and never if the
  caller joined it first. Conflicting join options raise `JoinConflictWarning` rather
  than passing silently. `Statement.unwrap()` returns the raw statement for the places
  SQLAlchemy inspects an argument's type.
- `@options` passes field keywords to the active backend verbatim; each namespace
  ships a stub pinning them to that backend's field constructor.
- `@skip_null` lets an explicit null -- or the strings `""`, `"null"`, `"none"` --
  switch off a filter that declares a default.
- Filters are inherited, so a project can define one base class and extend it.
- Typed: `py.typed` plus stubs for the three public namespaces.

[Unreleased]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/releases/tag/v0.1.0
