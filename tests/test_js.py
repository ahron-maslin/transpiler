from transpiler.frontend.javascript.parser import JSFrontend
from transpiler.backend.javascript.codegen import JSBackend
from transpiler.ir.nodes import *
from transpiler.ir.types import *


def test_js_frontend_parse():
    source_code = """
    function add(a, b) {
        return a + b;
    }
    """
    frontend = JSFrontend()
    program = frontend.parse(source_code)

    assert len(program.functions) == 1
    func = program.functions[0]
    assert func.name == "add"
    assert len(func.params) == 2
    assert func.params[0].name == "a"
    assert func.params[1].name == "b"
    assert isinstance(func.body.statements[0], Return)
    ret_val = func.body.statements[0].value
    assert isinstance(ret_val, Binary)
    assert ret_val.op == BinOp.ADD


def test_js_backend_generate():
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

    backend = JSBackend()
    code = backend.generate(program)

    expected = "function add(a, b) {\n    return (a + b);\n}\n"
    assert code.strip() == expected.strip()


def test_js_frontend_assign_complex():
    source_code = """
    function calc() {
        let a = 10;
        let b = 20;
        let c = (a + b) * 2;
        return c;
    }
    """
    frontend = JSFrontend()
    program = frontend.parse(source_code)

    func = program.functions[0]
    stmts = func.body.statements

    assert isinstance(stmts[0], Let)
    assert stmts[0].name == "a"
    assert isinstance(stmts[0].value, IntLiteral)

    assert isinstance(stmts[1], Let)
    assert stmts[1].name == "b"

    assert isinstance(stmts[2], Let)
    assert stmts[2].name == "c"
    val = stmts[2].value
    assert isinstance(val, Binary)
    assert val.op == BinOp.MUL
    assert isinstance(val.left, Binary)
    assert val.left.op == BinOp.ADD

    assert isinstance(stmts[3], Return)
    assert isinstance(stmts[3].value, Var)
    assert stmts[3].value.name == "c"
