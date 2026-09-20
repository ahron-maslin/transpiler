from pathlib import Path
from typing import Dict, Optional

from transpiler.ir.nodes import Function, GlobalVar, Program, Struct


class ProjectSymbolIndex:
    def __init__(self):
        # Global symbol mappings
        self.functions: Dict[str, Function] = {}
        self.structs: Dict[str, Struct] = {}
        self.globals: Dict[str, GlobalVar] = {}

        # Per-file symbols
        self.file_functions: Dict[Path, Dict[str, Function]] = {}
        self.file_structs: Dict[Path, Dict[str, Struct]] = {}
        self.file_globals: Dict[Path, Dict[str, GlobalVar]] = {}

    def add_program(self, rel_path: Path, program: Program) -> None:
        funcs: Dict[str, Function] = {}
        for func in program.functions:
            funcs[func.name] = func
            self.functions[func.name] = func

        structs: Dict[str, Struct] = {}
        for st in program.structs:
            structs[st.name] = st
            self.structs[st.name] = st

        globs: Dict[str, GlobalVar] = {}
        for g in program.globals:
            globs[g.name] = g
            self.globals[g.name] = g

        self.file_functions[rel_path] = funcs
        self.file_structs[rel_path] = structs
        self.file_globals[rel_path] = globs

    def get_external_functions(self, current_file: Optional[Path] = None) -> Dict[str, Function]:
        """Returns all functions defined in the project except those in current_file."""
        if current_file is None or current_file not in self.file_functions:
            return dict(self.functions)

        local_funcs = self.file_functions[current_file]
        return {name: func for name, func in self.functions.items() if name not in local_funcs}

    def clear(self) -> None:
        self.functions.clear()
        self.structs.clear()
        self.globals.clear()
        self.file_functions.clear()
        self.file_structs.clear()
        self.file_globals.clear()
