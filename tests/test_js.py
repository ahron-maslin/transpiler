from frontend.javascript.parser import JSFrontend
from backend.javascript.codegen import JSBackend
from ir.nodes import *
from ir.types import *

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
                body=Block([
                    Return(Binary(BinOp.ADD, Var("a"), Var("b")))
                ])
            )
        ]
    )
    
    backend = JSBackend()
    code = backend.generate(program)
    
    expected = "function add(a, b) {\n    return (a + b);\n}\n"
    assert code.strip() == expected.strip()
