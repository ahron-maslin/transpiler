import argparse
import os
import sys
from pathlib import Path

from transpiler.backend.c.codegen import CBackend
from transpiler.backend.go.codegen import GoBackend
from transpiler.backend.java.codegen import JavaBackend
from transpiler.backend.javascript.codegen import JSBackend
from transpiler.backend.python.codegen import PythonBackend
from transpiler.backend.rust.codegen import RustBackend
from transpiler.frontend.c.parser import CFrontend
from transpiler.frontend.go.parser import GoFrontend
from transpiler.frontend.java.parser import JavaFrontend
from transpiler.frontend.javascript.parser import JSFrontend
from transpiler.frontend.python.parser import PythonFrontend
from transpiler.frontend.rust.parser import RustFrontend
from transpiler.passes.type_inference import TypeInferencePass
from transpiler.project.config import ProjectConfig
from transpiler.project.converter import ProjectConverter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-Language Transpiler Framework")
    parser.add_argument(
        "input_path",
        nargs="?",
        default=None,
        help="Source file or directory to transpile",
    )
    parser.add_argument(
        "--to",
        choices=["go", "python", "js", "c", "rust", "java"],
        help="Target language",
    )
    parser.add_argument(
        "-o",
        "--out",
        "--output-dir",
        dest="output_dir",
        help="Target output directory (for projects) or file (for single file)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        help="Number of concurrent worker threads (0 = auto)",
    )
    parser.add_argument(
        "--from",
        dest="from_lang",
        choices=["go", "python", "js", "c", "rust", "java"],
        help="Source language filter",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="File inclusion glob pattern(s)",
    )
    parser.add_argument(
        "--exclude",
        "--ignore",
        dest="exclude",
        action="append",
        default=[],
        help="File exclusion glob pattern(s)",
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not respect .gitignore rules",
    )
    parser.add_argument(
        "--no-cache",
        "--no-incremental",
        dest="no_cache",
        action="store_true",
        help="Disable incremental build cache",
    )
    parser.add_argument(
        "--cache-file",
        help="Custom path for incremental build cache",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild of all files, ignoring cache",
    )
    parser.add_argument(
        "--copy-assets",
        action="store_true",
        help="Copy non-source asset files to target directory",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Do not generate project manifests (e.g. Cargo.toml, package.json)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately on first conversion failure",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate conversion without writing files to disk",
    )
    parser.add_argument(
        "--report",
        "--report-file",
        dest="report_file",
        help="Path to export conversion report as JSON",
    )
    parser.add_argument(
        "--config",
        help="Path to transpiler.json configuration file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show verbose per-file output",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    return parser


def run_single_file(input_path: str, target_lang: str, output_path: str | None = None):
    _, ext = os.path.splitext(input_path)

    with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
        source_code = f.read()

    frontend = None
    if ext == ".py":
        frontend = PythonFrontend()
    elif ext == ".js":
        frontend = JSFrontend()
    elif ext == ".c":
        frontend = CFrontend()
    elif ext == ".rs":
        frontend = RustFrontend()
    elif ext == ".go":
        frontend = GoFrontend()
    elif ext == ".java":
        frontend = JavaFrontend()
    else:
        print(f"Error: Unsupported source file extension '{ext}'", file=sys.stderr)
        sys.exit(1)

    try:
        ir_program = frontend.parse(source_code)
    except Exception as e:
        print(f"Frontend Error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    # Run passes
    TypeInferencePass().execute(ir_program)

    backend = None
    if target_lang == "go":
        backend = GoBackend()
    elif target_lang == "python":
        backend = PythonBackend()
    elif target_lang == "js":
        backend = JSBackend()
    elif target_lang == "c":
        backend = CBackend()
    elif target_lang == "rust":
        backend = RustBackend()
    elif target_lang == "java":
        backend = JavaBackend()

    try:
        target_code = backend.generate(ir_program)
        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(target_code)
        else:
            print(target_code)
    except Exception as e:
        print(f"Backend Error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


def run_project(args: argparse.Namespace):
    if args.config:
        config = ProjectConfig.from_file(args.config)
        # CLI overrides
        if args.input_path:
            config.source_dir = Path(args.input_path).resolve()
        if args.to:
            config.target_lang = args.to
        if args.output_dir:
            config.target_dir = Path(args.output_dir).resolve()
    else:
        source_path = Path(args.input_path).resolve()
        target_dir = (
            Path(args.output_dir).resolve()
            if args.output_dir
            else source_path.parent / f"{source_path.name}_{args.to}"
        )
        config = ProjectConfig(
            source_dir=source_path,
            target_dir=target_dir,
            target_lang=args.to,
            source_lang=args.from_lang,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
            respect_gitignore=not args.no_gitignore,
            jobs=args.jobs,
            incremental=not args.no_cache,
            cache_file=Path(args.cache_file) if args.cache_file else None,
            force=args.force,
            copy_assets=args.copy_assets,
            generate_manifest=not args.no_manifest,
            fail_fast=args.fail_fast,
            dry_run=args.dry_run,
            verbose=args.verbose,
            quiet=args.quiet,
        )

    converter = ProjectConverter(config)
    report = converter.run()

    if not config.quiet:
        report.print_summary(verbose=config.verbose)

    if args.report_file:
        report.save_json(Path(args.report_file))

    if not report.is_success:
        sys.exit(1)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.input_path and not args.config:
        parser.error("the following arguments are required: input_path (or --config)")

    if not args.to and not args.config:
        parser.error("the following arguments are required: --to (or --config)")

    input_path = args.input_path
    if input_path and not os.path.exists(input_path) and not args.config:
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Determine if single-file or project mode
    if input_path and os.path.isfile(input_path):
        run_single_file(input_path, args.to, args.output_dir)
    else:
        run_project(args)


if __name__ == "__main__":
    main()
