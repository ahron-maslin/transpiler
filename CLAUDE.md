# Transpiler — CLAUDE.md

Multi-language transpiler: parses source (C, Go, Java, JavaScript, Python, Rust) into a
shared IR, runs a type-inference pass, and generates source in any of those six languages.

**Read this before trusting the README.** The README describes this as "production-grade"
with "100% test coverage." Neither is currently true — see "Known state" below. Treat this
as an MVP skeleton: solid architecture, thin implementation.

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
  cli/main.py         argparse CLI: reads a file by extension, runs one frontend, the
                     type-inference pass, then one backend; prints to stdout only
```

Every frontend/backend file does `from transpiler.ir.nodes import *` and
`from transpiler.ir.types import *`. This is a deliberate (if debatable) convention across
the whole codebase, not a one-off — `pyproject.toml`'s ruff config disables F403/F405 to
match. If you add a new IR node name, check for collisions manually; the linter won't catch
shadowing.

## Known state (verified 2026-07-07 audit)

**Coverage claim is false.** README says 100%; actual `pytest --cov` is ~92%, with
individual frontends (JS 82%, Rust 84%, Java 85%, Go 87%) noticeably lower. Most existing
tests are shallow structural asserts (`isinstance(...)`, `expected in code`) rather than
semantic/round-trip checks — passing tests are weak evidence of correctness here.

**No backend emits several IR node types at all**: `For`, `Break`, `Continue`, `Cast`,
`StructInit`, `ArrayInit`, `MapInit`, `IndexAccess`, `Unary` are silently dropped (empty
string) by every one of the six `codegen.py` files. Don't assume "the IR supports X" means
"some backend can generate X" — grep the specific backend's `_generate_stmt`/
`_generate_expr` before relying on a construct.

**No backend does string escaping or reserved-word escaping.** A source string containing
`"`/`\`/newlines, or an identifier that collides with a target-language keyword
(`class`, `type`, `fn`, `match`, `yield`, `func`, `impl`...), produces broken or
non-compiling output. Treat generated code as untrusted until these are fixed.

**Frontends silently drop unhandled constructs instead of erroring.** E.g. Python's
`frontend/python/parser.py` has no handling for `for`, `try/except`, `with`, augmented
assignment, or multi-target assignment — unmatched AST nodes just return `None` and vanish
in `_visit_block`. Go's frontend treats C-style `for init;cond;update` as a bare
`while(cond)`, dropping init/update (an intentional-looking but dangerous simplification,
literally commented "for as while"). When touching a frontend, prefer raising/logging on an
unhandled node over silently continuing — the current silent-drop behavior is a footgun,
not a pattern to imitate in new code.

**CLI failure mode**: `cli/main.py` catches backend exceptions broadly and exits 1 on real
errors, but because of the silent-drop issue above, unsupported constructs don't raise at
all — you can get exit-code-0 with correct-looking but semantically wrong (or empty)
output. Don't treat "the CLI didn't error" as "the transpile was correct."

**Type inference (`passes/type_inference.py`) is shallow**: only walks
`Let/If/While/For` at the statement level (`Assign` is a no-op), and only a handful of
expression types. Don't assume inferred types are complete for structs, field access, or
values flowing through `Assign`.

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
  `test_deep_coverage.py` — when fixing a backend bug, check whether a test already
  (weakly) covers it before assuming untested.
- IR types are frozen-shape dataclasses; extend by adding a new `@dataclass` subclass of
  `Expr`/`Stmt` in `ir/nodes.py`, then wire it into every frontend that can produce it and
  every backend that should consume it — nothing enforces exhaustiveness, so grep after
  adding a variant to confirm all six backends handle it (or explicitly don't, on purpose).
