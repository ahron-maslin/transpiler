import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

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
from transpiler.ir.nodes import Program
from transpiler.passes.type_inference import TypeInferencePass
from transpiler.project.cache import IncrementalCache
from transpiler.project.config import (
    ProjectConfig,
    normalize_language,
    target_extension_for_lang,
)
from transpiler.project.indexer import ProjectSymbolIndex
from transpiler.project.manifest import generate_project_manifest
from transpiler.project.reporter import ConversionReport, FileResult
from transpiler.project.scanner import ProjectScanner


def get_frontend_for_extension(ext: str):
    ext = ext.lower()
    if ext == ".py":
        return PythonFrontend()
    elif ext == ".js":
        return JSFrontend()
    elif ext == ".c":
        return CFrontend()
    elif ext == ".rs":
        return RustFrontend()
    elif ext == ".go":
        return GoFrontend()
    elif ext == ".java":
        return JavaFrontend()
    raise ValueError(f"Unsupported source extension '{ext}'")


def get_backend_for_language(lang: str):
    norm = normalize_language(lang)
    if norm == "go":
        return GoBackend()
    elif norm == "python":
        return PythonBackend()
    elif norm == "js":
        return JSBackend()
    elif norm == "c":
        return CBackend()
    elif norm == "rust":
        return RustBackend()
    elif norm == "java":
        return JavaBackend()
    raise ValueError(f"Unsupported target language '{lang}'")


class ProjectConverter:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.scanner = ProjectScanner(config)
        self.cache = IncrementalCache(
            self.config.cache_file, enabled=self.config.incremental and not self.config.force
        )
        self.symbol_index = ProjectSymbolIndex()

    def run(self) -> ConversionReport:
        start_time = time.time()
        report = ConversionReport(
            source_dir=self.config.source_dir,
            target_dir=self.config.target_dir,
            target_lang=self.config.target_lang,
        )

        # 1. Scan source directory
        scan_result = self.scanner.scan()
        target_ext = target_extension_for_lang(self.config.target_lang)

        # 2. Identify cached vs files to transpile
        files_to_transpile: List[Tuple[Path, Path, Path]] = []
        for rel_path in scan_result.source_files:
            abs_source = self.config.source_dir / rel_path
            rel_target = rel_path.with_suffix(target_ext)
            abs_target = self.config.target_dir / rel_target

            if (
                not self.config.force
                and self.config.incremental
                and self.cache.is_cached(rel_path, abs_source, abs_target, self.config.target_lang)
            ):
                report.add_result(
                    FileResult(
                        status="SKIPPED",
                        source_path=rel_path,
                        target_path=rel_target,
                        loc=0,
                        duration_ms=0.0,
                    )
                )
            else:
                files_to_transpile.append((rel_path, abs_source, abs_target))

        # 3. Pre-scan & index symbols across all candidate files
        parsed_programs: Dict[Path, Program] = {}
        pre_errors: Dict[Path, Tuple[str, str]] = {}

        for rel_path, abs_source, _ in files_to_transpile:
            try:
                with open(abs_source, "r", encoding="utf-8", errors="ignore") as f:
                    source_code = f.read()
                frontend = get_frontend_for_extension(abs_source.suffix)
                ir_program = frontend.parse(source_code)
                parsed_programs[rel_path] = ir_program
                self.symbol_index.add_program(rel_path, ir_program)
            except Exception as e:
                pre_errors[rel_path] = (type(e).__name__, str(e))
                if self.config.fail_fast:
                    duration = time.time() - start_time
                    report.duration_seconds = duration
                    report.add_result(
                        FileResult(
                            status="FAILED",
                            source_path=rel_path,
                            error_type=type(e).__name__,
                            error_message=str(e),
                        )
                    )
                    return report

        # 4. Convert files (in parallel or sequentially)
        tasks = []
        for rel_path, abs_source, abs_target in files_to_transpile:
            if rel_path in pre_errors:
                err_type, err_msg = pre_errors[rel_path]
                report.add_result(
                    FileResult(
                        status="FAILED",
                        source_path=rel_path,
                        target_path=rel_path.with_suffix(target_ext),
                        error_type=err_type,
                        error_message=err_msg,
                    )
                )
                continue

            external_funcs = self.symbol_index.get_external_functions(rel_path)
            program = parsed_programs.get(rel_path)
            tasks.append((rel_path, abs_source, abs_target, program, external_funcs))

        def _worker(task_data):
            r_path, a_source, a_target, prog, ext_funcs = task_data
            t0 = time.time()
            try:
                # Count LOC
                loc = 0
                with open(a_source, "r", encoding="utf-8", errors="ignore") as f:
                    loc = sum(1 for line in f if line.strip())

                if prog is None:
                    with open(a_source, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()
                    frontend = get_frontend_for_extension(a_source.suffix)
                    prog = frontend.parse(code)

                # Type inference pass
                TypeInferencePass(external_functions=ext_funcs).execute(prog)

                # Backend code generation
                backend = get_backend_for_language(self.config.target_lang)
                target_code = backend.generate(prog)

                # Write output if not dry run
                if not self.config.dry_run:
                    a_target.parent.mkdir(parents=True, exist_ok=True)
                    with open(a_target, "w", encoding="utf-8") as f:
                        f.write(target_code)

                t1 = time.time()
                return FileResult(
                    status="SUCCESS",
                    source_path=r_path,
                    target_path=r_path.with_suffix(target_ext),
                    loc=loc,
                    duration_ms=(t1 - t0) * 1000,
                )
            except Exception as e:
                t1 = time.time()
                return FileResult(
                    status="FAILED",
                    source_path=r_path,
                    target_path=r_path.with_suffix(target_ext),
                    error_type=type(e).__name__,
                    error_message=str(e),
                    duration_ms=(t1 - t0) * 1000,
                )

        if tasks:
            if self.config.jobs == 1 or len(tasks) == 1:
                for task in tasks:
                    res = _worker(task)
                    report.add_result(res)
                    if res.status == "SUCCESS":
                        self.cache.record(
                            res.source_path,
                            self.config.source_dir / res.source_path,
                            self.config.target_dir / res.target_path,
                            self.config.target_lang,
                        )
                    elif self.config.fail_fast:
                        break
            else:
                max_workers = min(self.config.jobs, len(tasks))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_task = {executor.submit(_worker, t): t for t in tasks}
                    for future in as_completed(future_to_task):
                        res = future.result()
                        report.add_result(res)
                        if res.status == "SUCCESS":
                            self.cache.record(
                                res.source_path,
                                self.config.source_dir / res.source_path,
                                self.config.target_dir / res.target_path,
                                self.config.target_lang,
                            )
                        elif self.config.fail_fast:
                            # Cancel pending
                            for f in future_to_task:
                                f.cancel()
                            break

        # 5. Asset handling
        if self.config.copy_assets and not self.config.dry_run:
            for asset_rel in scan_result.asset_files:
                asset_src = self.config.source_dir / asset_rel
                asset_dst = self.config.target_dir / asset_rel
                try:
                    asset_dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(asset_src, asset_dst)
                    report.add_result(
                        FileResult(
                            status="ASSET_COPIED",
                            source_path=asset_rel,
                            target_path=asset_rel,
                        )
                    )
                except OSError as e:
                    report.add_result(
                        FileResult(
                            status="FAILED",
                            source_path=asset_rel,
                            target_path=asset_rel,
                            error_type=type(e).__name__,
                            error_message=str(e),
                        )
                    )

        # 6. Generate project manifest
        converted_rel_files = [
            r.target_path
            for r in report.file_results
            if r.status in ("SUCCESS", "SKIPPED") and r.target_path
        ]
        if self.config.generate_manifest and not self.config.dry_run:
            manifest_files = generate_project_manifest(
                self.config.target_dir,
                self.config.target_lang,
                project_name=self.config.source_dir.name,
                converted_files=converted_rel_files,
            )
            report.manifest_files.extend(manifest_files)

        # 7. Persist cache
        if not self.config.dry_run:
            self.cache.save()

        report.duration_seconds = time.time() - start_time
        return report
