import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO


@dataclass
class FileResult:
    status: str  # "SUCCESS", "SKIPPED", "FAILED", "ASSET_COPIED"
    source_path: Path
    target_path: Optional[Path] = None
    loc: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "source_path": self.source_path.as_posix(),
            "target_path": self.target_path.as_posix() if self.target_path else None,
            "loc": self.loc,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ConversionReport:
    source_dir: Path
    target_dir: Path
    target_lang: str
    file_results: List[FileResult] = field(default_factory=list)
    manifest_files: List[Path] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def total_scanned(self) -> int:
        return len(self.file_results)

    @property
    def converted_count(self) -> int:
        return sum(1 for r in self.file_results if r.status == "SUCCESS")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.file_results if r.status == "SKIPPED")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.file_results if r.status == "FAILED")

    @property
    def assets_copied_count(self) -> int:
        return sum(1 for r in self.file_results if r.status == "ASSET_COPIED")

    @property
    def total_loc(self) -> int:
        return sum(r.loc for r in self.file_results)

    @property
    def is_success(self) -> bool:
        return self.failed_count == 0

    def add_result(self, result: FileResult) -> None:
        self.file_results.append(result)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_dir": self.source_dir.as_posix(),
            "target_dir": self.target_dir.as_posix(),
            "target_lang": self.target_lang,
            "duration_seconds": round(self.duration_seconds, 3),
            "summary": {
                "total_scanned": self.total_scanned,
                "converted": self.converted_count,
                "skipped_cached": self.skipped_count,
                "failed": self.failed_count,
                "assets_copied": self.assets_copied_count,
                "manifest_files": [p.as_posix() for p in self.manifest_files],
                "total_loc": self.total_loc,
            },
            "files": [r.to_dict() for r in self.file_results],
        }

    def save_json(self, file_path: Path) -> None:
        file_path = Path(file_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def print_summary(self, out: Optional[TextIO] = None, verbose: bool = False) -> None:
        if out is None:
            out = sys.stdout

        rate = (
            (self.converted_count + self.skipped_count) / self.duration_seconds
            if self.duration_seconds > 0
            else 0.0
        )

        out.write("\n" + "=" * 55 + "\n")
        out.write("          PROJECT CONVERSION SUMMARY\n")
        out.write("=" * 55 + "\n")
        out.write(f"Source Directory:  {self.source_dir}\n")
        out.write(f"Target Directory:  {self.target_dir}\n")
        out.write(f"Target Language:   {self.target_lang}\n")
        out.write("-" * 55 + "\n")
        out.write(f"Files Processed:   {self.total_scanned}\n")
        out.write(f"  - Transpiled:    {self.converted_count}\n")
        out.write(f"  - Cached/Skip:   {self.skipped_count}\n")
        out.write(f"  - Assets Copied: {self.assets_copied_count}\n")
        out.write(f"  - Failed:        {self.failed_count}\n")
        if self.manifest_files:
            out.write(f"Manifest Files:    {len(self.manifest_files)}\n")
        out.write(f"Total LOC:         {self.total_loc:,}\n")
        out.write(f"Duration:          {self.duration_seconds:.2f}s ({rate:.1f} files/s)\n")
        out.write("=" * 55 + "\n")

        failures = [r for r in self.file_results if r.status == "FAILED"]
        if failures:
            out.write("\nFailures:\n")
            for f in failures:
                out.write(f"  ✖ {f.source_path}: {f.error_type}: {f.error_message}\n")
            out.write("\n")

        if verbose:
            out.write("\nDetailed File Status:\n")
            for r in self.file_results:
                icon = {
                    "SUCCESS": "✔",
                    "SKIPPED": "↷",
                    "ASSET_COPIED": "📄",
                    "FAILED": "✖",
                }.get(r.status, "•")
                out.write(
                    f"  {icon} [{r.status}] {r.source_path} ({r.loc} LOC, {r.duration_ms:.1f}ms)\n"
                )
            out.write("\n")
