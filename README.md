# Transpiler

A multi-language transpiler framework written in Python. This project provides a set of frontends for parsing various programming languages into a common Intermediate Representation (IR), and backends for generating code in multiple target languages from that IR.

## Features
- **Frontends**: Parse C, Go, Java, JavaScript, Python, and Rust source code.
- **Backends**: Generate C, Go, Java, JavaScript, Python, and Rust code.
- **Passes**: Type inference and other intermediate representation passes.

## Installation

You can install `transpiler` directly from PyPI (once published) or build it locally.

### Local Installation

Clone the repository and install using `pip`:

```bash
git clone https://github.com/developer/transpiler.git
cd transpiler
pip install .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

Use the CLI to transpile a source file to a target language:

```bash
transpiler source_file.js --to python
```

### Supported Languages
- `c`
- `go`
- `java`
- `js`
- `python`
- `rust`

## Development

Run tests using pytest:
```bash
pytest
```

Format code using black:
```bash
black src/ tests/
```

Lint using ruff:
```bash
ruff check src/ tests/
```
