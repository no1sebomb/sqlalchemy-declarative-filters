# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/no1sebomb/sqlalchemy-declarative-filters/releases/tag/v0.1.0
