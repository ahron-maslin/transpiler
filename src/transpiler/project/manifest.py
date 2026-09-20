import json
import re
from pathlib import Path
from typing import List, Optional

from transpiler.project.config import normalize_language


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", name).lower()
    return cleaned.strip("_-") or "transpiled_project"


def generate_project_manifest(
    target_dir: Path,
    target_lang: str,
    project_name: Optional[str] = None,
    converted_files: Optional[List[Path]] = None,
) -> List[Path]:
    """
    Generates target-language scaffolding/manifests in target_dir if they don't already exist.
    Returns list of paths created.
    """
    created: List[Path] = []
    if converted_files is not None and len(converted_files) == 0:
        return created

    target_dir.mkdir(parents=True, exist_ok=True)
    norm_lang = normalize_language(target_lang)
    p_name = sanitize_project_name(project_name or target_dir.name)

    if norm_lang == "rust":
        cargo_path = target_dir / "Cargo.toml"
        if not cargo_path.exists():
            cargo_content = f"""[package]
name = "{p_name}"
version = "0.1.0"
edition = "2021"

[dependencies]
"""
            cargo_path.write_text(cargo_content, encoding="utf-8")
            created.append(cargo_path)

    elif norm_lang == "js":
        pkg_path = target_dir / "package.json"
        if not pkg_path.exists():
            pkg_content = {
                "name": p_name,
                "version": "1.0.0",
                "description": "Transpiled project",
                "main": "index.js",
                "type": "module",
            }
            pkg_path.write_text(json.dumps(pkg_content, indent=2), encoding="utf-8")
            created.append(pkg_path)

    elif norm_lang == "go":
        mod_path = target_dir / "go.mod"
        if not mod_path.exists():
            mod_content = f"""module {p_name}

go 1.20
"""
            mod_path.write_text(mod_content, encoding="utf-8")
            created.append(mod_path)

    elif norm_lang == "python":
        # Ensure __init__.py exists in all subdirectories containing .py files
        dirs_to_check = set()
        if converted_files:
            for rel_file in converted_files:
                if rel_file.suffix == ".py":
                    parent = (target_dir / rel_file).parent
                    while parent != target_dir and target_dir in parent.parents:
                        dirs_to_check.add(parent)
                        parent = parent.parent
                    if parent == target_dir:
                        dirs_to_check.add(target_dir)
        else:
            for py_file in target_dir.rglob("*.py"):
                dirs_to_check.add(py_file.parent)

        for d in dirs_to_check:
            init_file = d / "__init__.py"
            if not init_file.exists():
                init_file.write_text("# Transpiled Python package\n", encoding="utf-8")
                created.append(init_file)

    return created
