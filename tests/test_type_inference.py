from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.passes.type_inference import TypeInferencePass

def test_type_inference_let_literal():
    # Let x: Any = 10
    program = Program(
        functions=[
            Function(
                name="main",
                params=[],
                return_type=VoidType,
                body=Block([
                    Let(name="x", type=AnyType, value=IntLiteral(10))
                ])
            )
        ]
    )
    
    TypeInferencePass().execute(program)
    
    let_stmt = program.functions[0].body.statements[0]
    assert let_stmt.type.kind == TypeKind.INT

def test_type_inference_let_binary():
    # Let y: Any = x + 5 (where x is Int)
    program = Program(
        functions=[
            Function(
                name="main",
                params=[Param("x", IntType)],
                return_type=VoidType,
                body=Block([
                    Let(name="y", type=AnyType, value=Binary(BinOp.ADD, Var("x"), IntLiteral(5)))
                ])
            )
        ]
    )
    
    TypeInferencePass().execute(program)
    
    let_stmt = program.functions[0].body.statements[0]
    assert let_stmt.type.kind == TypeKind.INT
