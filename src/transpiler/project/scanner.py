import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from transpiler.project.config import (
    DEFAULT_EXCLUDES,
    EXTENSION_TO_LANG,
    LANGUAGE_EXTENSIONS,
    ProjectConfig,
)


@dataclass
class ScanResult:
    source_files: List[Path] = field(default_factory=list)
    asset_files: List[Path] = field(default_factory=list)
    ignored_files: List[Path] = field(default_factory=list)
    language_counts: Dict[str, int] = field(default_factory=dict)
    total_loc: int = 0


class GitignoreMatcher:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.rules: List[tuple[str, bool, bool]] = []  # (pattern, is_negation, is_dir_only)
        self._load_gitignore(self.base_dir / ".gitignore")

    def _load_gitignore(self, gitignore_path: Path):
        if not gitignore_path.is_file():
            return
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    is_negation = False
                    if line.startswith("!"):
                        is_negation = True
                        line = line[1:]
                    is_dir_only = False
                    if line.endswith("/"):
                        is_dir_only = True
                        line = line[:-1]
                    if line.startswith("/"):
                        line = line[1:]
                    self.rules.append((line, is_negation, is_dir_only))
        except OSError:
            pass

    def is_ignored(self, rel_path: Path, is_dir: bool = False) -> bool:
        norm_path = rel_path.as_posix()
        name = rel_path.name
        ignored = False

        for pattern, is_negation, is_dir_only in self.rules:
            if is_dir_only and not is_dir:
                continue

            matches = False
            if "/" in pattern:
                if fnmatch.fnmatch(norm_path, pattern) or fnmatch.fnmatch(
                    norm_path, f"**/{pattern}"
                ):
                    matches = True
            else:
                if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(norm_path, f"*/{pattern}"):
                    matches = True

            if matches:
                ignored = not is_negation

        return ignored


class ProjectScanner:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.source_dir = config.source_dir
        self.gitignore_matcher = (
            GitignoreMatcher(self.source_dir) if config.respect_gitignore else None
        )
        self.all_excludes = list(DEFAULT_EXCLUDES) + list(config.exclude_patterns)

    def _is_excluded_by_patterns(self, rel_path: Path, is_dir: bool = False) -> bool:
        norm_path = rel_path.as_posix()
        name = rel_path.name

        for pat in self.all_excludes:
            clean_pat = pat.rstrip("/")
            if fnmatch.fnmatch(name, clean_pat) or fnmatch.fnmatch(norm_path, clean_pat):
                return True
            if fnmatch.fnmatch(norm_path, f"**/{clean_pat}") or fnmatch.fnmatch(
                norm_path, f"**/{clean_pat}/**"
            ):
                return True

        if self.gitignore_matcher and self.gitignore_matcher.is_ignored(rel_path, is_dir=is_dir):
            return True

        return False

    def _matches_includes(self, rel_path: Path) -> bool:
        if not self.config.include_patterns:
            return True
        norm_path = rel_path.as_posix()
        name = rel_path.name
        for pat in self.config.include_patterns:
            if (
                fnmatch.fnmatch(name, pat)
                or fnmatch.fnmatch(norm_path, pat)
                or fnmatch.fnmatch(norm_path, f"**/{pat}")
            ):
                return True
        return False

    def scan(self) -> ScanResult:
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")

        result = ScanResult()
        target_lang_ext: Optional[str] = None
        if self.config.source_lang:
            target_lang_ext = LANGUAGE_EXTENSIONS.get(self.config.source_lang)

        # Walk through directory
        for root, dirs, files in os_walk_filtered(self):
            root_path = Path(root)
            for file_name in files:
                abs_file = root_path / file_name
                try:
                    rel_file = abs_file.relative_to(self.source_dir)
                except ValueError:
                    continue

                if self._is_excluded_by_patterns(rel_file, is_dir=False):
                    result.ignored_files.append(rel_file)
                    continue

                ext = abs_file.suffix.lower()
                is_source = ext in EXTENSION_TO_LANG

                if is_source:
                    if target_lang_ext and ext != target_lang_ext:
                        # Excluded because source_lang filter was applied
                        result.ignored_files.append(rel_file)
                        continue

                    if not self._matches_includes(rel_file):
                        result.ignored_files.append(rel_file)
                        continue

                    result.source_files.append(rel_file)
                    lang = EXTENSION_TO_LANG[ext]
                    result.language_counts[lang] = result.language_counts.get(lang, 0) + 1

                    # Count LOC
                    try:
                        with open(abs_file, "r", encoding="utf-8", errors="ignore") as f:
                            lines = sum(1 for line in f if line.strip())
                            result.total_loc += lines
                    except OSError:
                        pass
                else:
                    result.asset_files.append(rel_file)

        # Sort files for deterministic ordering
        result.source_files.sort()
        result.asset_files.sort()
        result.ignored_files.sort()
        return result


def os_walk_filtered(scanner: ProjectScanner):
    import os

    for root, dirs, files in os.walk(scanner.source_dir):
        root_path = Path(root)
        # Filter dirs in-place to avoid descending into excluded folders
        filtered_dirs = []
        for d in dirs:
            dir_abs = root_path / d
            try:
                dir_rel = dir_abs.relative_to(scanner.source_dir)
            except ValueError:
                continue
            if not scanner._is_excluded_by_patterns(dir_rel, is_dir=True):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs
        yield root, dirs, files
