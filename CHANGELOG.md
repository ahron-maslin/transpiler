# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-08
### Fixed
- All 6 backends (C, Go, Java, JavaScript, Python, Rust) now emit `For`, `Break`,
  `Continue`, `Cast`, `StructInit`, `ArrayInit`, `MapInit`, `IndexAccess`, and `Unary`,
  which were previously silently rendered as empty output.
- All 6 backends now escape string literals and rename identifiers that collide with
  target-language keywords.
- Python backend: `and`/`or` no longer emit invalid `&&`/`||` syntax.
- Go backend: struct field export preserves internal casing (`userID` -> `UserID`).
- Java backend: functions named `main` are only treated as the program entry point when
  they take no parameters; struct/class definitions are now emitted (previously dropped).
- C backend: `print()` dispatches to the correctly-typed runtime function instead of
  always assuming an `int` argument.
- Go frontend: for-loops (both C-style and condition-only) and multi-target
  assignment/declaration now parse correctly; the condition-only form was previously
  silently becoming an infinite loop.
- C and JavaScript frontends: `else` branches are no longer silently dropped.
- Rust frontend: `if`/`while`/`loop` are now parsed instead of silently becoming no-ops;
  range-based `for`-loops are supported.
- Python frontend: `for x in range(...)`, augmented assignment, multi-target assignment,
  and module-level globals are now supported; unsupported constructs (`try`/`except`,
  `with`, non-range iteration) now raise a clear error instead of silently vanishing.
- C, Go, Java, and JavaScript frontends now parse function call expressions at all --
  previously `print(x)` / `fmt.Println(x)` / `System.out.println(x)` / `console.log(x)`
  silently disappeared from every one of those four languages' output.
### Changed
- README's "production-grade"/"100% test coverage" claims corrected to reflect reality.

## [0.1.1] - 2026-05-13
### Changed
- Deprecated Python 3.9 support (minimum now 3.10).
- Unified CI/CD linting and formatting via `pre-commit`.
- Updated `tree-sitter` and grammar dependencies for better ABI support.
- Stabilized CI pipeline with synchronized local and remote checks.

## [0.1.0] - 2026-04-28
### Added
- Multi-language transpiler framework.
- Frontends for C, Go, Java, JavaScript, Python, and Rust.
- Backends for generating C, Go, Java, JavaScript, Python, and Rust.
- Intermediate Representation (IR) and type inference pass.
- PyPI packaging setup.
