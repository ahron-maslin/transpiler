from transpiler.frontend.rust.parser import RustFrontend
from transpiler.backend.rust.codegen import RustBackend
from transpiler.ir.nodes import *
from transpiler.ir.types import *

def test_rust_frontend_parse():
    source_code = """
    fn add(a: i32, b: i32) -> i32 {
        return a + b;
    }
    """
    frontend = RustFrontend()
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

def test_rust_backend_generate():
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
    
    backend = RustBackend()
    code = backend.generate(program)
    
    expected = "fn add(a: i32, b: i32) -> i32 {\n    return (a + b);\n}\n"
    assert expected.strip() in code.strip()
