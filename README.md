# Transpiler 🚀

An experimental multi-language transpiler framework. Parse source code from one language into a language-agnostic Intermediate Representation (IR), apply semantic passes, and generate source code in your target language.

[![CI](https://github.com/ahron-maslin/transpiler/actions/workflows/ci.yml/badge.svg)](https://github.com/ahron-maslin/transpiler/actions)
[![PyPI](https://img.shields.io/pypi/v/transpiler.svg)](https://pypi.org/project/transpiler/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **Multi-Source Parsing**: Support for C, Go, Java, JavaScript, and Rust via tree-sitter, and Python via the standard library `ast` module.
- **Language-Agnostic IR**: An internal representation covering common control flow, structs, arrays, maps, and casts.
- **Intelligent Passes**: A basic type-inference pass for `Any`-typed locals.
- **Cross-Language Generation**: Code generation for all six supported target languages, covering the common subset of each language's control flow and literal syntax.

This project is under active development. It handles core control flow (if/while/for/break/continue), function calls, structs, and casts across all six languages, but does not yet support exceptions, `with`/context-manager blocks, or non-range iteration in `for` loops — unsupported constructs raise a clear error at parse time rather than silently producing wrong output. See `CLAUDE.md` for the current, detailed list of what is and isn't supported.

## 🛠 Installation

### From PyPI
```bash
pip install transpiler
```

### From Source
```bash
git clone https://github.com/ahron-maslin/transpiler.git
cd transpiler
pip install .
```

For development (including testing and linting tools):
```bash
pip install -e ".[dev]"
```

## 🚀 Quick Start

Use the `transpiler` CLI to convert code instantly:

```bash
# Convert a Python script to JavaScript
transpiler example.py --to js

# Convert a C header to Rust
transpiler header.c --to rust
```

### Example
**Input (Python):**
```python
def fib(n: int) -> int:
    if n <= 1: return n
    return fib(n - 1) + fib(n - 2)
```

**Command:**
```bash
transpiler fib.py --to js
```

**Output (JavaScript):**
```javascript
function fib(n) {
    if ((n <= 1)) {
        return n;
    }
    return (fib((n - 1)) + fib((n - 2)));
}
```

## 📁 Large-Scale Project Conversion

Transpile entire multi-file codebases while preserving directory structure, handling cross-file symbol indexing, and generating target-language project manifests:

```bash
# Convert a Python project to Rust
transpiler ./my_python_project --to rust -o ./my_rust_project

# Convert with parallel workers and asset copying
transpiler ./src --to js -o ./dist -j 8 --copy-assets

# Dry-run preview with JSON report export
transpiler ./src --to go -o ./dist --dry-run --report report.json
```

### Key Capabilities

- **Parallel Processing**: Multi-worker concurrent conversion across CPU cores (`-j` / `--jobs`).
- **Incremental Caching**: SHA-256 content hashing skips unchanged files on subsequent runs (`--incremental`, `--force`).
- **Fault-Tolerant Resilience**: Reports per-file status without aborting conversion of valid files (`--fail-fast` available).
- **Target Manifest Generation**: Automatically generates `Cargo.toml` (Rust), `package.json` (JavaScript), `go.mod` (Go), or `__init__.py` (Python).
- **Project Configuration**: Load settings from `transpiler.json` (`--config transpiler.json`).
- **Ignore & Gitignore Support**: Respects `.gitignore` rules and custom exclusion patterns (`--exclude`).

### Project Configuration File (`transpiler.json`)

```json
{
  "source_dir": "src",
  "target_dir": "dist",
  "target_lang": "rust",
  "jobs": 4,
  "copy_assets": true,
  "include": ["**/*.py"],
  "exclude": ["**/tests/**"]
}
```

Run with:
```bash
transpiler --config transpiler.json
```

## 🧪 Development

We value code quality and maintainability.

### Running Tests
```bash
pytest
```

### Linting & Formatting
We use **Ruff** for linting and **Black** for formatting.
```bash
black src/ tests/
ruff check src/ tests/
```

### Pre-commit Hooks
Ensure your changes meet our standards before committing:
```bash
pre-commit install
```

## 📦 CI/CD

- **CI**: Every PR and push to `master` triggers our GitHub Actions suite, testing on Python 3.10-3.12.
- **Releases**: Automated PyPI publishing on tag creation (e.g., `git tag v0.1.0 && git push origin v0.1.0`).

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
