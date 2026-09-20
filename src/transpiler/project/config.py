import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# Canonical mappings for target and source languages
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    "python": ".py",
    "py": ".py",
    "javascript": ".js",
    "js": ".js",
    "c": ".c",
    "rust": ".rs",
    "rs": ".rs",
    "go": ".go",
    "java": ".java",
}

EXTENSION_TO_LANG: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".c": "c",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
}

DEFAULT_EXCLUDES: List[str] = [
    ".git*",
    ".hg*",
    ".svn*",
    "__pycache__*",
    "*.pyc",
    "*.pyo",
    ".venv*",
    "venv*",
    "node_modules*",
    ".pytest_cache*",
    ".mypy_cache*",
    ".ruff_cache*",
    "build*",
    "dist*",
    "target*",
    ".idea*",
    ".vscode*",
    ".DS_Store",
    "*.lock",
]


def normalize_language(lang: str) -> str:
    lang_lower = lang.strip().lower()
    aliases = {
        "py": "python",
        "js": "js",
        "javascript": "js",
        "rs": "rust",
    }
    return aliases.get(lang_lower, lang_lower)


def target_extension_for_lang(target_lang: str) -> str:
    norm = normalize_language(target_lang)
    mapping = {
        "python": ".py",
        "js": ".js",
        "c": ".c",
        "rust": ".rs",
        "go": ".go",
        "java": ".java",
    }
    if norm not in mapping:
        raise ValueError(f"Unsupported target language: {target_lang}")
    return mapping[norm]


@dataclass
class ProjectConfig:
    source_dir: Path
    target_dir: Path
    target_lang: str
    source_lang: Optional[str] = None
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    respect_gitignore: bool = True
    jobs: int = 0
    incremental: bool = True
    cache_file: Optional[Path] = None
    force: bool = False
    copy_assets: bool = False
    generate_manifest: bool = True
    fail_fast: bool = False
    dry_run: bool = False
    verbose: bool = False
    quiet: bool = False

    def __post_init__(self):
        self.source_dir = Path(self.source_dir).resolve()
        self.target_dir = Path(self.target_dir).resolve()
        self.target_lang = normalize_language(self.target_lang)
        if self.source_lang:
            self.source_lang = normalize_language(self.source_lang)
        if self.jobs <= 0:
            cpu_count = os.cpu_count() or 1
            self.jobs = min(32, cpu_count + 4)
        if self.cache_file is not None:
            self.cache_file = Path(self.cache_file).resolve()
        else:
            self.cache_file = self.target_dir / ".transpiler_cache.json"

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Optional[Path] = None) -> "ProjectConfig":
        base = base_dir if base_dir else Path.cwd()
        source_dir_raw = data.get("source_dir", ".")
        source_dir = Path(source_dir_raw)
        if not source_dir.is_absolute():
            source_dir = (base / source_dir).resolve()

        target_dir_raw = data.get("target_dir", "out")
        target_dir = Path(target_dir_raw)
        if not target_dir.is_absolute():
            target_dir = (base / target_dir).resolve()

        target_lang = data.get("target_lang") or data.get("to")
        if not target_lang:
            raise ValueError("target_lang (or 'to') must be specified in config")

        cache_file_raw = data.get("cache_file")
        cache_file = None
        if cache_file_raw:
            p = Path(cache_file_raw)
            cache_file = p if p.is_absolute() else (base / p).resolve()

        return cls(
            source_dir=source_dir,
            target_dir=target_dir,
            target_lang=target_lang,
            source_lang=data.get("source_lang"),
            include_patterns=data.get("include_patterns") or data.get("include") or [],
            exclude_patterns=data.get("exclude_patterns") or data.get("exclude") or [],
            respect_gitignore=data.get("respect_gitignore", True),
            jobs=data.get("jobs", 0),
            incremental=data.get("incremental", True),
            cache_file=cache_file,
            force=data.get("force", False),
            copy_assets=data.get("copy_assets", False),
            generate_manifest=data.get("generate_manifest", True),
            fail_fast=data.get("fail_fast", False),
            dry_run=data.get("dry_run", False),
            verbose=data.get("verbose", False),
            quiet=data.get("quiet", False),
        )

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "ProjectConfig":
        path = Path(config_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, base_dir=path.parent)
