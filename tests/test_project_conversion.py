import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from transpiler.cli.main import main
from transpiler.ir.nodes import Block, Function, IntLiteral, Program, Return, Var
from transpiler.ir.types import IntType, StringType
from transpiler.passes.type_inference import TypeInferencePass
from transpiler.project.cache import IncrementalCache
from transpiler.project.config import (
    ProjectConfig,
    normalize_language,
    target_extension_for_lang,
)
from transpiler.project.converter import ProjectConverter
from transpiler.project.indexer import ProjectSymbolIndex
from transpiler.project.manifest import generate_project_manifest
from transpiler.project.reporter import ConversionReport, FileResult
from transpiler.project.scanner import GitignoreMatcher, ProjectScanner


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


def test_project_config_defaults(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    tgt = tmp_path / "tgt"

    cfg = ProjectConfig(source_dir=src, target_dir=tgt, target_lang="javascript")
    assert cfg.target_lang == "js"
    assert cfg.incremental is True
    assert cfg.force is False
    assert cfg.jobs > 0
    assert cfg.cache_file == tgt / ".transpiler_cache.json"


def test_project_config_from_file(tmp_path):
    config_file = tmp_path / "transpiler.json"
    config_data = {
        "source_dir": "source",
        "target_dir": "dist",
        "target_lang": "rust",
        "jobs": 2,
        "copy_assets": True,
        "include": ["**/*.py"],
        "exclude": ["**/tests/**"],
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    cfg = ProjectConfig.from_file(config_file)
    assert cfg.source_dir == (tmp_path / "source").resolve()
    assert cfg.target_dir == (tmp_path / "dist").resolve()
    assert cfg.target_lang == "rust"
    assert cfg.jobs == 2
    assert cfg.copy_assets is True
    assert cfg.include_patterns == ["**/*.py"]
    assert cfg.exclude_patterns == ["**/tests/**"]


def test_language_helpers():
    assert normalize_language("py") == "python"
    assert normalize_language("javascript") == "js"
    assert normalize_language("rs") == "rust"
    assert target_extension_for_lang("rust") == ".rs"
    assert target_extension_for_lang("python") == ".py"
    assert target_extension_for_lang("js") == ".js"
    assert target_extension_for_lang("go") == ".go"
    assert target_extension_for_lang("c") == ".c"
    assert target_extension_for_lang("java") == ".java"

    with pytest.raises(ValueError):
        target_extension_for_lang("unsupported_lang")


# ---------------------------------------------------------------------------
# Scanner & Gitignore Tests
# ---------------------------------------------------------------------------


def test_gitignore_matcher(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\n/build/\n!important.log\nnode_modules/\n")

    matcher = GitignoreMatcher(tmp_path)
    assert matcher.is_ignored(Path("test.log")) is True
    assert matcher.is_ignored(Path("important.log")) is False
    assert matcher.is_ignored(Path("build"), is_dir=True) is True
    assert matcher.is_ignored(Path("other/dir/app.py")) is False


def test_project_scanner(tmp_path):
    src = tmp_path / "project"
    src.mkdir()
    (src / "main.py").write_text("def main(): pass\n")
    pkg = src / "pkg"
    pkg.mkdir()
    (pkg / "util.py").write_text("x = 1\n")
    (pkg / "config.json").write_text('{"key": "val"}')
    hidden = src / ".git"
    hidden.mkdir()
    (hidden / "index").write_text("git")

    cfg = ProjectConfig(source_dir=src, target_dir=tmp_path / "out", target_lang="js")
    scanner = ProjectScanner(cfg)
    res = scanner.scan()

    assert Path("main.py") in res.source_files
    assert Path("pkg/util.py") in res.source_files
    assert Path("pkg/config.json") in res.asset_files
    # .git directory is excluded
    assert not any(".git" in p.as_posix() for p in res.source_files)
    assert res.language_counts.get("python") == 2
    assert res.total_loc >= 2


def test_scanner_with_include_and_exclude(tmp_path):
    src = tmp_path / "project"
    src.mkdir()
    (src / "app.py").write_text("a = 1")
    (src / "app_test.py").write_text("test = 1")
    (src / "helper.js").write_text("console.log(1);")

    cfg = ProjectConfig(
        source_dir=src,
        target_dir=tmp_path / "out",
        target_lang="rust",
        source_lang="python",
        exclude_patterns=["*_test.py"],
    )
    scanner = ProjectScanner(cfg)
    res = scanner.scan()

    assert Path("app.py") in res.source_files
    assert Path("app_test.py") not in res.source_files
    assert Path("helper.js") not in res.source_files


# ---------------------------------------------------------------------------
# Incremental Cache Tests
# ---------------------------------------------------------------------------


def test_incremental_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache = IncrementalCache(cache_file, enabled=True)

    src_file = tmp_path / "foo.py"
    src_file.write_text("def foo(): return 42\n")
    tgt_file = tmp_path / "foo.js"
    tgt_file.write_text("function foo() { return 42; }")

    rel = Path("foo.py")
    assert not cache.is_cached(rel, src_file, tgt_file, "js")

    cache.record(rel, src_file, tgt_file, "js")
    cache.save()

    # Reload cache
    cache2 = IncrementalCache(cache_file, enabled=True)
    assert cache2.is_cached(rel, src_file, tgt_file, "js")

    # Mismatch target lang
    assert not cache2.is_cached(rel, src_file, tgt_file, "rust")

    # Target file removed
    tgt_file.unlink()
    assert not cache2.is_cached(rel, src_file, tgt_file, "js")

    # Recreate target file and modify source file
    tgt_file.write_text("recreated")
    src_file.write_text("def foo(): return 999\n")
    assert not cache2.is_cached(rel, src_file, tgt_file, "js")


# ---------------------------------------------------------------------------
# Symbol Indexer & Cross-File Type Inference
# ---------------------------------------------------------------------------


def test_symbol_indexer():
    index = ProjectSymbolIndex()
    f1 = Function(
        name="get_number",
        params=[],
        return_type=IntType,
        body=Block(statements=[Return(value=IntLiteral(42))]),
    )
    prog1 = Program(functions=[f1])
    index.add_program(Path("math.py"), prog1)

    f2 = Function(
        name="greet",
        params=[],
        return_type=StringType,
        body=Block(statements=[]),
    )
    prog2 = Program(functions=[f2])
    index.add_program(Path("greet.py"), prog2)

    assert "get_number" in index.functions
    assert "greet" in index.functions

    ext_for_math = index.get_external_functions(Path("math.py"))
    assert "greet" in ext_for_math
    assert "get_number" not in ext_for_math


def test_type_inference_with_external_functions():
    ext_func = Function(
        name="fetch_id",
        params=[],
        return_type=IntType,
        body=Block(statements=[]),
    )
    ext_funcs = {"fetch_id": ext_func}

    # In single file, let x = fetch_id()
    # In pure single-file inference without ext_funcs, type of fetch_id() was AnyType
    from transpiler.ir.nodes import Call, Let

    var_x = Var("fetch_id")
    let_stmt = Let(name="x", type=IntType, value=Call(function=var_x, args=[]))
    test_func = Function(
        name="caller",
        params=[],
        return_type=IntType,
        body=Block(statements=[let_stmt, Return(value=Var("x"))]),
    )
    prog = Program(functions=[test_func])

    inf_pass = TypeInferencePass(external_functions=ext_funcs)
    inf_pass.execute(prog)

    # Inferred call return type matches fetch_id's return type
    assert inf_pass.functions["fetch_id"].return_type == IntType


# ---------------------------------------------------------------------------
# Manifest Generation Tests
# ---------------------------------------------------------------------------


def test_manifest_generation(tmp_path):
    out_rust = tmp_path / "out_rust"
    out_rust.mkdir()
    gen_rust = generate_project_manifest(out_rust, "rust", project_name="my_test")
    assert len(gen_rust) == 1
    cargo = out_rust / "Cargo.toml"
    assert cargo.exists()
    assert 'name = "my_test"' in cargo.read_text()

    out_js = tmp_path / "out_js"
    out_js.mkdir()
    gen_js = generate_project_manifest(out_js, "js", project_name="my_test")
    assert len(gen_js) == 1
    pkg = out_js / "package.json"
    assert pkg.exists()
    assert '"name": "my_test"' in pkg.read_text()

    out_go = tmp_path / "out_go"
    out_go.mkdir()
    gen_go = generate_project_manifest(out_go, "go", project_name="my_test")
    assert len(gen_go) == 1
    mod = out_go / "go.mod"
    assert mod.exists()
    assert "module my_test" in mod.read_text()

    out_py = tmp_path / "out_py"
    pkg_sub = out_py / "subpkg"
    pkg_sub.mkdir(parents=True)
    (pkg_sub / "mod.py").write_text("x = 1")
    generate_project_manifest(out_py, "python")
    assert (pkg_sub / "__init__.py").exists()


# ---------------------------------------------------------------------------
# ConversionReport Tests
# ---------------------------------------------------------------------------


def test_conversion_report(tmp_path):
    report = ConversionReport(
        source_dir=tmp_path / "src",
        target_dir=tmp_path / "dist",
        target_lang="rust",
    )
    report.add_result(
        FileResult(
            status="SUCCESS",
            source_path=Path("main.py"),
            target_path=Path("main.rs"),
            loc=10,
            duration_ms=5.0,
        )
    )
    report.add_result(
        FileResult(
            status="SKIPPED",
            source_path=Path("util.py"),
            target_path=Path("util.rs"),
            loc=5,
        )
    )
    report.add_result(
        FileResult(
            status="FAILED",
            source_path=Path("broken.py"),
            error_type="SyntaxError",
            error_message="invalid syntax",
        )
    )

    assert report.total_scanned == 3
    assert report.converted_count == 1
    assert report.skipped_count == 1
    assert report.failed_count == 1
    assert not report.is_success

    # Export to dict and JSON
    d = report.to_dict()
    assert d["summary"]["converted"] == 1
    assert d["summary"]["failed"] == 1

    json_file = tmp_path / "report.json"
    report.save_json(json_file)
    assert json_file.exists()


# ---------------------------------------------------------------------------
# ProjectConverter End-to-End Tests
# ---------------------------------------------------------------------------


def test_project_converter_end_to_end(tmp_path):
    src = tmp_path / "my_code"
    src.mkdir()
    (src / "math_helper.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    sub = src / "core"
    sub.mkdir()
    (sub / "calc.py").write_text("def calc() -> int:\n    return add(2, 3)\n")
    (src / "config.json").write_text('{"env": "test"}')

    tgt = tmp_path / "my_code_js"
    cfg = ProjectConfig(
        source_dir=src,
        target_dir=tgt,
        target_lang="js",
        copy_assets=True,
        jobs=2,
    )

    converter = ProjectConverter(cfg)
    report = converter.run()

    assert report.is_success
    assert report.converted_count == 2
    assert report.assets_copied_count == 1
    assert (tgt / "math_helper.js").exists()
    assert (tgt / "core" / "calc.js").exists()
    assert (tgt / "config.json").exists()
    assert (tgt / "package.json").exists()

    math_js = (tgt / "math_helper.js").read_text()
    assert "function add(a, b)" in math_js

    # Test incremental run
    converter2 = ProjectConverter(cfg)
    report2 = converter2.run()
    assert report2.is_success
    assert report2.skipped_count == 2
    assert report2.converted_count == 0

    # Test force rebuild
    cfg_force = ProjectConfig(
        source_dir=src,
        target_dir=tgt,
        target_lang="js",
        force=True,
    )
    converter3 = ProjectConverter(cfg_force)
    report3 = converter3.run()
    assert report3.converted_count == 2
    assert report3.skipped_count == 0


def test_project_converter_dry_run(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.py").write_text("def test(): pass\n")
    tgt = tmp_path / "out"

    cfg = ProjectConfig(
        source_dir=src,
        target_dir=tgt,
        target_lang="rust",
        dry_run=True,
    )
    converter = ProjectConverter(cfg)
    report = converter.run()

    assert report.is_success
    assert report.converted_count == 1
    assert not tgt.exists()  # Nothing should be written to disk


def test_project_converter_fault_tolerance(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "good.py").write_text("def good() -> int: return 1\n")
    (src / "broken.py").write_text("def broken() :::: bad syntax\n")
    tgt = tmp_path / "out"

    # Default: continue on error
    cfg = ProjectConfig(
        source_dir=src,
        target_dir=tgt,
        target_lang="python",
        fail_fast=False,
    )
    converter = ProjectConverter(cfg)
    report = converter.run()

    assert not report.is_success
    assert report.converted_count == 1
    assert report.failed_count == 1
    assert (tgt / "good.py").exists()

    # Fail fast: stops immediately
    tgt_ff = tmp_path / "out_ff"
    cfg_ff = ProjectConfig(
        source_dir=src,
        target_dir=tgt_ff,
        target_lang="python",
        fail_fast=True,
    )
    converter_ff = ProjectConverter(cfg_ff)
    report_ff = converter_ff.run()
    assert not report_ff.is_success


# ---------------------------------------------------------------------------
# CLI Project Integration Tests
# ---------------------------------------------------------------------------


def test_cli_project_conversion(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def run() -> int:\n    return 42\n")
    tgt = tmp_path / "dist"
    rep_file = tmp_path / "report.json"

    with patch.object(
        sys,
        "argv",
        [
            "transpiler",
            str(src),
            "--to",
            "go",
            "-o",
            str(tgt),
            "--report",
            str(rep_file),
            "--verbose",
        ],
    ):
        main()

    assert (tgt / "app.go").exists()
    assert (tgt / "go.mod").exists()
    assert rep_file.exists()
    out, err = capsys.readouterr()
    assert "PROJECT CONVERSION SUMMARY" in out
    assert "app.go" in (tgt / "app.go").name


def test_cli_project_conversion_failure_exit(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "broken.py").write_text("def broken() :::: bad\n")
    tgt = tmp_path / "dist"

    with patch.object(
        sys,
        "argv",
        [
            "transpiler",
            str(src),
            "--to",
            "go",
            "-o",
            str(tgt),
            "--quiet",
        ],
    ):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1


def test_cli_project_config_file(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text("def hello() -> str: return 'hi'\n")
    tgt = tmp_path / "dist"

    config_path = tmp_path / "transpiler.json"
    config_path.write_text(
        json.dumps(
            {
                "source_dir": str(src),
                "target_dir": str(tgt),
                "target_lang": "rust",
            }
        )
    )

    with patch.object(sys, "argv", ["transpiler", "--config", str(config_path)]):
        main()

    assert (tgt / "hello.rs").exists()
    assert (tgt / "Cargo.toml").exists()


def test_converter_helpers():
    from transpiler.project.converter import (
        get_backend_for_language,
        get_frontend_for_extension,
    )

    for ext in [".py", ".js", ".c", ".rs", ".go", ".java"]:
        assert get_frontend_for_extension(ext) is not None

    with pytest.raises(ValueError):
        get_frontend_for_extension(".unknown")

    for lang in ["go", "python", "js", "c", "rust", "java"]:
        assert get_backend_for_language(lang) is not None

    with pytest.raises(ValueError):
        get_backend_for_language("unknown_lang")


def test_config_validation_errors(tmp_path):
    with pytest.raises(ValueError):
        ProjectConfig.from_dict({"source_dir": "."})

    with pytest.raises(FileNotFoundError):
        ProjectConfig.from_file(tmp_path / "non_existent_config.json")


def test_scanner_missing_dir(tmp_path):
    cfg = ProjectConfig(
        source_dir=tmp_path / "missing",
        target_dir=tmp_path / "out",
        target_lang="python",
    )
    scanner = ProjectScanner(cfg)
    with pytest.raises(FileNotFoundError):
        scanner.scan()


def test_cache_clear(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache = IncrementalCache(cache_file)
    src = tmp_path / "a.py"
    src.write_text("x = 1")
    tgt = tmp_path / "a.js"
    tgt.write_text("var x = 1;")
    cache.record(Path("a.py"), src, tgt, "js")
    cache.save()
    assert cache_file.exists()
    cache.clear()
    assert not cache_file.exists()
    assert len(cache.entries) == 0


def test_symbol_index_clear():
    idx = ProjectSymbolIndex()
    idx.functions["test"] = Function(
        name="test", params=[], return_type=IntType, body=Block(statements=[])
    )
    assert len(idx.functions) == 1
    idx.clear()
    assert len(idx.functions) == 0


def test_project_converter_jobs_1(tmp_path):
    src = tmp_path / "single_job_src"
    src.mkdir()
    (src / "f1.py").write_text("def f1(): pass\n")
    (src / "f2.py").write_text("def f2(): pass\n")
    tgt = tmp_path / "single_job_tgt"

    cfg = ProjectConfig(
        source_dir=src,
        target_dir=tgt,
        target_lang="js",
        jobs=1,
    )
    converter = ProjectConverter(cfg)
    rep = converter.run()
    assert rep.is_success
    assert rep.converted_count == 2


def test_reporter_verbose_and_failures(tmp_path, capsys):
    rep = ConversionReport(
        source_dir=tmp_path / "src",
        target_dir=tmp_path / "out",
        target_lang="rust",
        duration_seconds=1.0,
    )
    rep.add_result(
        FileResult(
            status="SUCCESS",
            source_path=Path("ok.py"),
            target_path=Path("ok.rs"),
            loc=5,
            duration_ms=2.0,
        )
    )
    rep.add_result(
        FileResult(
            status="FAILED",
            source_path=Path("fail.py"),
            error_type="CustomError",
            error_message="failed to convert",
        )
    )
    rep.print_summary(verbose=True)
    out, _ = capsys.readouterr()
    assert "CustomError: failed to convert" in out
    assert "[SUCCESS] ok.py" in out
