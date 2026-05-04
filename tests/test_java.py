from transpiler.frontend.java.parser import JavaFrontend
from transpiler.backend.java.codegen import JavaBackend
from transpiler.ir.nodes import *
from transpiler.ir.types import *

def test_java_frontend_parse():
    source_code = """
    class Main {
        public static int add(int a, int b) {
            return a + b;
        }
    }
    """
    frontend = JavaFrontend()
    program = frontend.parse(source_code)
    
    assert len(program.functions) == 1
    func = program.functions[0]
    assert func.name == "add"
    assert len(func.params) == 2
    assert func.params[0].name == "a"
    assert func.params[0].type.kind == TypeKind.INT
    assert isinstance(func.body.statements[0], Return)
    ret_val = func.body.statements[0].value
    assert isinstance(ret_val, Binary)
    assert ret_val.op == BinOp.ADD

def test_java_backend_generate():
    program = Program(
        functions=[
            Function(
                name="add",
                params=[Param("a", IntType), Param("b", IntType)],
                return_type=IntType,
                body=Block([
                    Return(Binary(BinOp.ADD, Var("a"), Var("b")))
                ])
            )
        ]
    )
    
    backend = JavaBackend()
    code = backend.generate(program)
    
    expected = "public static int add(int a, int b) {\n        return (a + b);\n    }"
    assert expected.strip() in code.strip()
