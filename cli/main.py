import argparse
import sys
import os

from frontend.python.parser import PythonFrontend
from frontend.javascript.parser import JSFrontend
from frontend.c.parser import CFrontend
from frontend.rust.parser import RustFrontend
from frontend.go.parser import GoFrontend
from frontend.java.parser import JavaFrontend
from backend.go.codegen import GoBackend
from backend.python.codegen import PythonBackend
from backend.javascript.codegen import JSBackend
from backend.c.codegen import CBackend
from backend.rust.codegen import RustBackend
from backend.java.codegen import JavaBackend
from passes.type_inference import TypeInferencePass

def main():
    parser = argparse.ArgumentParser(description="Multi-Language Transpiler Framework")
    parser.add_argument("input_file", help="Source file to transpile")
    parser.add_argument("--to", required=True, choices=["go", "python", "js", "c", "rust", "java"], help="Target language")
    
    args = parser.parse_args()
    
    input_path = args.input_file
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    _, ext = os.path.splitext(input_path)
    
    with open(input_path, "r") as f:
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
        print(f"Frontend Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Run passes
    TypeInferencePass().execute(ir_program)
        
    backend = None
    if args.to == "go":
        backend = GoBackend()
    elif args.to == "python":
        backend = PythonBackend()
    elif args.to == "js":
        backend = JSBackend()
    elif args.to == "c":
        backend = CBackend()
    elif args.to == "rust":
        backend = RustBackend()
    elif args.to == "java":
        backend = JavaBackend()
        
    try:
        target_code = backend.generate(ir_program)
        print(target_code)
    except Exception as e:
        print(f"Backend Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
