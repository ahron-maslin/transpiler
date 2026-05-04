import os
import glob
import re

directories = ["src/transpiler", "tests"]
modules = ["frontend", "backend", "ir", "passes", "runtime", "cli"]

def update_imports():
    for d in directories:
        for filepath in glob.glob(f"{d}/**/*.py", recursive=True):
            with open(filepath, "r") as f:
                content = f.read()
                
            original = content
            for mod in modules:
                # Replace 'from module' with 'from transpiler.module'
                content = re.sub(rf"^from {mod}\b", f"from transpiler.{mod}", content, flags=re.MULTILINE)
                # Replace 'import module' with 'import transpiler.module'
                content = re.sub(rf"^import {mod}\b", f"import transpiler.{mod}", content, flags=re.MULTILINE)
            
            if original != content:
                print(f"Updating {filepath}")
                with open(filepath, "w") as f:
                    f.write(content)

if __name__ == "__main__":
    update_imports()
