import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


class IncrementalCache:
    def __init__(self, cache_file: Optional[Path] = None, enabled: bool = True):
        self.cache_file = (cache_file or Path(".transpiler_cache.json")).resolve()
        self.enabled = enabled
        self.entries: Dict[str, Dict[str, Any]] = {}
        if self.enabled:
            self.load()

    def load(self) -> None:
        if not self.cache_file.is_file():
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "entries" in data:
                    self.entries = data["entries"]
                elif isinstance(data, dict):
                    self.entries = data
        except (OSError, json.JSONDecodeError):
            self.entries = {}

    def save(self) -> None:
        if not self.enabled:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "entries": self.entries}, f, indent=2)
            temp_file.replace(self.cache_file)
        except OSError:
            pass

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def is_cached(
        self,
        rel_path: Path,
        abs_source_path: Path,
        abs_target_path: Path,
        target_lang: str,
    ) -> bool:
        if not self.enabled:
            return False

        key = rel_path.as_posix()
        if key not in self.entries:
            return False

        entry = self.entries[key]
        if entry.get("target_lang") != target_lang:
            return False

        if not abs_target_path.exists():
            return False

        try:
            # Check modification time first for fast bailout
            curr_mtime = abs_source_path.stat().st_mtime
            if curr_mtime == entry.get("mtime"):
                return True

            curr_hash = self.compute_file_hash(abs_source_path)
            if curr_hash == entry.get("hash"):
                # Update mtime in cache
                entry["mtime"] = curr_mtime
                return True
        except OSError:
            return False

        return False

    def record(
        self,
        rel_path: Path,
        abs_source_path: Path,
        abs_target_path: Path,
        target_lang: str,
        status: str = "success",
    ) -> None:
        if not self.enabled:
            return

        key = rel_path.as_posix()
        try:
            mtime = abs_source_path.stat().st_mtime
            h = self.compute_file_hash(abs_source_path)
            self.entries[key] = {
                "hash": h,
                "mtime": mtime,
                "target_lang": target_lang,
                "target_file": abs_target_path.as_posix(),
                "status": status,
            }
        except OSError:
            pass

    def clear(self) -> None:
        self.entries = {}
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
            except OSError:
                pass
