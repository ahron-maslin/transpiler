from frontend.go.parser import GoFrontend
from backend.go.codegen import GoBackend
from ir.nodes import *
from ir.types import *

def test_go_frontend_parse():
    source_code = """
    package main
    func add(a int, b int) int {
        return a + b
    }
    """
    frontend = GoFrontend()
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

def test_go_backend_generate():
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
    
    backend = GoBackend()
    code = backend.generate(program)
    
    expected = "func add(a int, b int) int {\n\treturn (a + b)\n}\n"
    assert expected.strip() in code.strip()
