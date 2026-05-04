# Contributing to Transpiler

First off, thanks for taking the time to contribute!

## Development Setup

1. Fork the repo and clone it locally.
2. Install the dependencies: `pip install -e ".[dev]"`
3. Install pre-commit hooks: `pre-commit install` (if using pre-commit)

## Running Tests

We use `pytest` for testing.

```bash
pytest
```

## Linting and Formatting

We use `ruff` for linting and `black` for formatting.

```bash
black src/ tests/
ruff check src/ tests/
```

Please make sure all tests, linting, and formatting checks pass before submitting a pull request.
