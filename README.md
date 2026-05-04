# Transpiler 🚀

A production-grade, multi-language transpiler framework. Parse source code from one language into a language-agnostic Intermediate Representation (IR), apply semantic passes, and generate source code in your target language.

[![CI](https://github.com/ahron-maslin/transpiler/actions/workflows/ci.yml/badge.svg)](https://github.com/ahron-maslin/transpiler/actions)
[![PyPI](https://img.shields.io/pypi/v/transpiler.svg)](https://pypi.org/project/transpiler/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- **Multi-Source Parsing**: Support for C, Go, Java, JavaScript, Python, and Rust via tree-sitter.
- **Language-Agnostic IR**: A robust internal representation that preserves semantics across paradigms.
- **Intelligent Passes**: Built-in type inference and semantic analysis to ensure correctness.
- **Cross-Language Generation**: High-quality code generation for all supported target languages.
- **Production Ready**: Fully type-hinted, linted with Ruff, and verified with 100% test coverage.

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

- **CI**: Every PR and push to `main` triggers our GitHub Actions suite, testing on Python 3.9-3.12.
- **Releases**: Automated PyPI publishing on tag creation (e.g., `git tag v0.1.0 && git push origin v0.1.0`).

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
