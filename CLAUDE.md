# Transpiler — CLAUDE.md

Multi-language transpiler: parses source (C, Go, Java, JavaScript, Python, Rust) into a
shared IR, runs a type-inference pass, and generates source in any of those six languages.

**Read this before trusting the README.** An earlier version of the README claimed
"production-grade" and "100% test coverage" — both were false (see git history). The README
has since been corrected. Treat this as an actively-developed transpiler with real but
bounded language coverage: see "Known state" below for exactly what is and isn't supported.

## Architecture

```
src/transpiler/
  ir/nodes.py       dataclass AST: literals, Binary/Unary, Call, FieldAccess, IndexAccess,
                     StructInit/ArrayInit/MapInit, Cast, Let/Assign/If/While/For/Return/
                     Break/Continue, Function/Struct/GlobalVar/Program
  ir/types.py        Type system: TypeKind enum + PrimitiveType/ArrayType/MapType/
                     StructType/FunctionType/OptionalType
  frontend/<lang>/parser.py   source -> IR. Python uses stdlib `ast`; C/Go/Java/JS/Rust
                     use tree-sitter (tree_sitter_<lang> + Language(tsX.language())).
  passes/type_inference.py    single shallow forward pass over each function body
  backend/<lang>/codegen.py   IR -> source string
  project/                    large-scale project conversion subsystem: scanner,
                             incremental cache, symbol indexer, manifest generator,
                             reporter, and concurrent converter
  cli/main.py         argparse CLI: supports single-file conversion (prints to stdout
                             or file) and multi-file project conversion across directories
```

Every frontend/backend file does `from transpiler.ir.nodes import *` and
`from transpiler.ir.types import *`. This is a deliberate (if debatable) convention across
the whole codebase, not a one-off — `pyproject.toml`'s ruff config disables F403/F405 to
match. If you add a new IR node name, check for collisions manually; the linter won't catch
shadowing.

## Known state (fixed 2026-07-07, superseding the earlier audit)

**Coverage**: `pytest --cov` is ~86% (263 tests). Coverage dropped from the previously
measured 92% not because tests were removed, but because a large amount of previously-dead
code (backend node handlers, frontend control-flow branches) is now live and not every new
branch has a test yet — a lower number here reflects more real surface area, not less
testing. Re-run `pytest --cov=transpiler --cov-report=term-missing` before trusting this
figure if it's been a while.

**All 6 backends now emit `For`, `Break`, `Continue`, `Cast`, `StructInit`, `ArrayInit`,
`MapInit`, `IndexAccess`, `Unary`** (previously silently dropped as empty strings). Notes on
the translation strategy: Python and Rust have no native C-style `for`, so `For` is
downleveled to an `init` statement followed by a `while` loop with the `update` appended to
the end of the body — if you touch this, preserve the ordering (init before the loop,
update as the last statement in the body) or `break`/`continue` semantics inside the loop
will silently change. `Cast`/`ArrayInit`/`MapInit` codegen for Go/Java/C has no element-type
info on the IR (`ArrayInit`/`MapInit` don't carry one), so those backends fall back to
`interface{}`/`Object[]`/`Map.of(...)`-style untyped containers — this is a known, accepted
simplification, not a bug to "fix" without first extending the IR.

**All 6 backends now escape string literals** (backslash/quote/newline/tab/CR via
`backend/common.py:escape_c_style`/`escape_python_str`) **and rename identifiers that
collide with target-language keywords** (`backend/common.py:safe_ident` + the
`*_KEYWORDS` sets, e.g. a source function named `class` becomes `class_` in Python output).
Every backend's `_name()` method is the enforcement point — if you add a new place an
identifier is emitted, route it through `_name()`.

**Frontends now raise `NotImplementedError` on genuinely unsupported constructs** instead of
silently dropping them (the prior behavior was the single biggest correctness problem in
this codebase — e.g. Rust's `if`/`while`/`loop` were entirely unhandled and silently became
no-ops, and **none of C/Go/Java/JS ever parsed a function call expression at all**, meaning
`print(x)`/`fmt.Println(x)`/`System.out.println(x)`/`console.log(x)` silently vanished from
every one of those four languages' output — this was more severe than the original audit
realized). What's now genuinely supported: `if`/`while`/`for`/`break`/`continue`, function
calls (including qualified calls like `fmt.Println`/`System.out.println`), unary
expressions, and — Go specifically — multi-target assignment/declaration (staged through
temporaries so `a, b = b, a` swaps correctly rather than executing sequentially). What's
still explicitly unsupported and raises rather than silently drops: Python `try`/`except`/
`with`, `for` over anything but `range(...)`, Rust `for` over anything but an integer range,
and JS destructuring assignment. Comments (`comment`/`line_comment`/`block_comment` node
types) are the one deliberate exception to "raise on unhandled" — they're recognized and
silently ignored in every frontend, not a bug.

**Go's `for` parsing was worse than previously documented**: even the "supported"
while-style `for cond { }` was silently becoming `for true { }` (an infinite loop) because
`child_by_field_name("condition")` returns `None` for that shape — the condition is a
positional (unnamed-field) child, not a named field, unless the loop has a C-style
`for_clause`. Fixed in `frontend/go/parser.py`; if you touch Go for-loop parsing again,
re-verify field vs. positional access against the actual tree-sitter-go grammar rather than
assuming `condition`/`initializer`/`update` are always real fields (they aren't uniformly).

**CLI (`cli/main.py`)** now surfaces real errors: since frontends/backends raise instead of
silently producing wrong output, `Frontend Error: NotImplementedError: ...` /
`Backend Error: ...` (with exception type name included) reliably means something is
actually unsupported, and a non-zero exit code now reliably means the transpile did not
succeed. You can trust "the CLI didn't error" much more than before, though `ArrayInit`/
`MapInit`'s untyped-container fallback (above) can still produce output that doesn't
type-check in a statically-typed target even though the CLI itself succeeds.

**Type inference (`passes/type_inference.py`) is still shallow** (unchanged by this pass):
only walks `Let/If/While/For` at the statement level (`Assign` is a no-op), and only a
handful of expression types. Don't assume inferred types are complete for structs, field
access, or values flowing through `Assign`. The C backend's print-argument-type dispatch
(`print_str`/`print_float`/`print_bool`/`print_int`) works around this locally by tracking
its own `self.var_types` during codegen rather than relying on the shared pass — a pattern
you may need to repeat if another backend needs better-than-`Any` type info.

**Tree-sitter versions are currently consistent** (pyproject pins `tree-sitter>=0.24.0`,
resolves to 0.25.2; all native frontends use the matching `Language(tsX.language())` call
convention). Git history shows 5+ commits fighting version/ABI mismatches — if you touch
frontend parser construction, know that `Language()`'s calling convention differs across
tree-sitter 0.21 / 0.22+ / 0.24+, and re-check both `pyproject.toml` and `uv.lock` resolve
to versions that agree with whatever API the parser code calls.

**mypy has been progressively loosened**, not fixed: `pyproject.toml`'s `[tool.mypy]`
disables `union-attr`, `assignment`, `attr-defined` repo-wide (see commit "chore: silence
noisy mypy errors in CI"). These were likely masking real bugs from the star-import +
`Optional`-heavy code rather than being genuinely unhelpful — be skeptical of mypy silence
in files using those patterns.

## Dev workflow

```bash
pip install -e ".[dev]"        # requires Python >=3.10 — do not use a 3.9 venv
pre-commit install
pytest                          # or: pytest --cov=transpiler --cov-report=term-missing
black src/ tests/
ruff check src/ tests/
```

CI (`.github/workflows/ci.yml`) runs pre-commit (trailing-whitespace, black, ruff, mypy)
+ pytest on Python 3.10/3.11/3.12 for every push/PR to `master`, and publishes to PyPI via
trusted publishing on `v*` tags. No separate coverage gate — coverage regressions won't
fail CI.

Local note: any pre-existing `.venv`/`.venv39` in this repo may be stale (a Python 3.9 venv
with tree-sitter not installed has been seen here, which can't satisfy `requires-python =
">=3.10"`) — recreate rather than trust an existing venv if installs/imports fail oddly.

## Conventions

- TDD-style tests exist per language (`tests/test_<lang>.py`) plus `test_edge_cases.py` /
  `test_deep_coverage.py` / `test_bugfixes.py` — when fixing a backend bug, check whether a
  test already (weakly) covers it before assuming untested. `test_bugfixes.py` specifically
  holds regression tests for the correctness-gap fixes described above — it's the reference
  for what "supported" is currently expected to mean for each construct.
- IR types are frozen-shape dataclasses; extend by adding a new `@dataclass` subclass of
  `Expr`/`Stmt` in `ir/nodes.py`, then wire it into every frontend that can produce it and
  every backend that should consume it — nothing enforces exhaustiveness, so grep after
  adding a variant to confirm all six backends handle it (or explicitly don't, on purpose).
