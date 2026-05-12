from transpiler.frontend.python.parser import PythonFrontend
from transpiler.backend.python.codegen import PythonBackend
from transpiler.ir.nodes import *
from transpiler.ir.types import *

def test_python_frontend_parse():
    source_code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    frontend = PythonFrontend()
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

def test_python_backend_generate():
    program = Program(
        functions=[
            Function(
                name="add",
                params=[Param("a", IntType), Param("b", IntType)],
                return_type=IntType,
                body=Block([Return(Binary(BinOp.ADD, Var("a"), Var("b")))]),
            )
        ]
    )

    backend = PythonBackend()
    code = backend.generate(program)

    expected = "def add(a: int, b: int) -> int:\n    return (a + b)"
    assert expected.strip() in code.strip()

def test_python_frontend_assign_complex():
    source_code = """
def calc() -> int:
    a: int = 10
    b = 20
    c = (a + b) * 2
    return c
"""
    frontend = PythonFrontend()
    program = frontend.parse(source_code)

    func = program.functions[0]
    stmts = func.body.statements

    assert isinstance(stmts[0], Let)
    assert stmts[0].name == "a"
    assert stmts[0].type.kind == TypeKind.INT
    assert isinstance(stmts[0].value, IntLiteral)
    assert stmts[0].value.value == 10

    assert isinstance(stmts[1], Assign)
    assert isinstance(stmts[1].target, Var)
    assert stmts[1].target.name == "b"
    assert isinstance(stmts[1].value, IntLiteral)

    assert isinstance(stmts[2], Assign)
    assert stmts[2].target.name == "c"
    val = stmts[2].value
    assert isinstance(val, Binary)
    assert val.op == BinOp.MUL
    assert isinstance(val.left, Binary)
    assert val.left.op == BinOp.ADD

def test_python_backend_assign_complex():
    program = Program(
        functions=[
            Function(
                name="calc",
                params=[],
                return_type=IntType,
                body=Block([
                    Let("a", IntType, IntLiteral(10)),
                    Assign(Var("b"), IntLiteral(20)),
                    Assign(Var("c"), Binary(BinOp.MUL, Binary(BinOp.ADD, Var("a"), Var("b")), IntLiteral(2))),
                    Return(Var("c"))
                ])
            )
        ]
    )
    backend = PythonBackend()
    code = backend.generate(program)

    assert "a: int = 10" in code
    assert "b = 20" in code
    assert "c = ((a + b) * 2)" in code
    assert "return c" in code
