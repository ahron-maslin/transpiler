# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
