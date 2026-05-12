"""Backend codegen tests for Go, Rust, Java, JS — control flow, literals, structs."""
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.backend.go.codegen import GoBackend
from transpiler.backend.rust.codegen import RustBackend
from transpiler.backend.java.codegen import JavaBackend
from transpiler.backend.javascript.codegen import JSBackend


def _prog(stmts, params=None, ret=VoidType, name="test_fn"):
    return Program(functions=[
        Function(name, params or [], ret, Block(stmts))
    ])


# ---------------------------------------------------------------------------
# Go backend
# ---------------------------------------------------------------------------

class TestGoBackend:
    def test_if_else(self):
        prog = _prog([
            If(Binary(BinOp.GT, Var("x"), IntLiteral(0)),
               then_block=Block([Return(IntLiteral(1))]),
               else_block=Block([Return(IntLiteral(0))]))
        ], params=[Param("x", IntType)], ret=IntType)
        code = GoBackend().generate(prog)
        assert "if (x > 0)" in code
        assert "return 1" in code
        assert "} else {" in code
        assert "return 0" in code

    def test_while_as_for(self):
        prog = _prog([
            While(Binary(BinOp.LT, Var("i"), IntLiteral(10)),
                  body=Block([Assign(Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1)))]))
        ])
        code = GoBackend().generate(prog)
        assert "for (i < 10)" in code
        assert "i = (i + 1)" in code

    def test_let_declaration(self):
        prog = _prog([Let("x", IntType, IntLiteral(42))])
        code = GoBackend().generate(prog)
        assert "var x int = 42" in code

    def test_assign(self):
        prog = _prog([Assign(Var("x"), IntLiteral(99))])
        code = GoBackend().generate(prog)
        assert "x = 99" in code

    def test_nil_literal(self):
        prog = _prog([Return(NullLiteral())])
        code = GoBackend().generate(prog)
        assert "return nil" in code

    def test_bool_literals(self):
        prog = _prog([
            Let("a", BoolType, BoolLiteral(True)),
            Let("b", BoolType, BoolLiteral(False)),
        ])
        code = GoBackend().generate(prog)
        assert "true" in code
        assert "false" in code

    def test_string_literal(self):
        prog = _prog([Return(StringLiteral("hello"))])
        code = GoBackend().generate(prog)
        assert '"hello"' in code

    def test_float_literal(self):
        prog = _prog([Return(FloatLiteral(3.14))])
        code = GoBackend().generate(prog)
        assert "3.14" in code

    def test_call(self):
        prog = _prog([ExprStmt(Call(Var("add"), [IntLiteral(1), IntLiteral(2)]))])
        code = GoBackend().generate(prog)
        assert "add(1, 2)" in code

    def test_print_call_mapped(self):
        prog = _prog([ExprStmt(Call(Var("print"), [StringLiteral("hi")]))])
        code = GoBackend().generate(prog)
        assert "fmt.Println" in code

    def test_field_access_capitalized(self):
        prog = _prog([Return(FieldAccess(Var("p"), "x"))])
        code = GoBackend().generate(prog)
        assert "p.X" in code

    def test_struct(self):
        prog = Program(structs=[Struct("Point", [("x", IntType), ("y", FloatType)])])
        code = GoBackend().generate(prog)
        assert "type Point struct" in code
        assert "X int" in code
        assert "Y float64" in code

    def test_void_return(self):
        prog = _prog([Return()])
        code = GoBackend().generate(prog)
        assert "return" in code

    def test_type_mapping(self):
        b = GoBackend()
        assert b._type_to_str(IntType) == "int"
        assert b._type_to_str(FloatType) == "float64"
        assert b._type_to_str(BoolType) == "bool"
        assert b._type_to_str(StringType) == "string"
        assert b._type_to_str(VoidType) == "void"
        assert b._type_to_str(AnyType) == "interface{}"

    def test_package_and_import_header(self):
        prog = _prog([Return()])
        code = GoBackend().generate(prog)
        assert "package main" in code
        assert 'import "fmt"' in code

    def test_expr_statement(self):
        prog = _prog([ExprStmt(Var("x"))])
        code = GoBackend().generate(prog)
        assert "x" in code


# ---------------------------------------------------------------------------
# Rust backend
# ---------------------------------------------------------------------------

class TestRustBackend:
    def test_if_else(self):
        prog = _prog([
            If(Binary(BinOp.GT, Var("x"), IntLiteral(0)),
               then_block=Block([Return(IntLiteral(1))]),
               else_block=Block([Return(IntLiteral(0))]))
        ], params=[Param("x", IntType)], ret=IntType)
        code = RustBackend().generate(prog)
        assert "if (x > 0)" in code
        assert "return 1;" in code
        assert "} else {" in code
        assert "return 0;" in code

    def test_while(self):
        prog = _prog([
            While(Binary(BinOp.LT, Var("i"), IntLiteral(10)),
                  body=Block([Assign(Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1)))]))
        ])
        code = RustBackend().generate(prog)
        assert "while (i < 10)" in code
        assert "i = (i + 1);" in code

    def test_let_declaration(self):
        prog = _prog([Let("x", IntType, IntLiteral(42))])
        code = RustBackend().generate(prog)
        assert "let mut x: i32 = 42;" in code

    def test_assign(self):
        prog = _prog([Assign(Var("x"), IntLiteral(99))])
        code = RustBackend().generate(prog)
        assert "x = 99;" in code

    def test_none_literal(self):
        prog = _prog([Return(NullLiteral())])
        code = RustBackend().generate(prog)
        assert "return None;" in code

    def test_bool_literals(self):
        prog = _prog([Return(BoolLiteral(True)), Return(BoolLiteral(False))])
        code = RustBackend().generate(prog)
        assert "return true;" in code
        assert "return false;" in code

    def test_string_literal_to_string(self):
        prog = _prog([Return(StringLiteral("hello"))])
        code = RustBackend().generate(prog)
        assert '"hello".to_string()' in code

    def test_float_literal(self):
        prog = _prog([Return(FloatLiteral(2.71))])
        code = RustBackend().generate(prog)
        assert "2.71" in code

    def test_call(self):
        prog = _prog([ExprStmt(Call(Var("add"), [IntLiteral(1), IntLiteral(2)]))])
        code = RustBackend().generate(prog)
        assert "add(1, 2);" in code

    def test_print_call_mapped(self):
        prog = _prog([ExprStmt(Call(Var("print"), [Var("x")]))])
        code = RustBackend().generate(prog)
        assert 'println!("{}", x)' in code

    def test_field_access(self):
        prog = _prog([Return(FieldAccess(Var("p"), "x"))])
        code = RustBackend().generate(prog)
        assert "p.x" in code

    def test_struct(self):
        prog = Program(structs=[Struct("Point", [("x", IntType), ("y", FloatType)])])
        code = RustBackend().generate(prog)
        assert "struct Point" in code
        assert "x: i32," in code
        assert "y: f64," in code

    def test_void_return(self):
        prog = _prog([Return()])
        code = RustBackend().generate(prog)
        assert "return;" in code

    def test_return_type_omitted_for_void(self):
        prog = _prog([Return()], ret=VoidType)
        code = RustBackend().generate(prog)
        assert "fn test_fn()" in code
        assert "->" not in code.split("{")[0]

    def test_type_mapping(self):
        b = RustBackend()
        assert b._type_to_str(IntType) == "i32"
        assert b._type_to_str(FloatType) == "f64"
        assert b._type_to_str(BoolType) == "bool"
        assert b._type_to_str(StringType) == "String"
        assert b._type_to_str(VoidType) == "()"
        assert b._type_to_str(StructType("Foo")) == "Foo"
        assert "Any" in b._type_to_str(AnyType)

    def test_expr_statement(self):
        prog = _prog([ExprStmt(Var("x"))])
        code = RustBackend().generate(prog)
        assert "x;" in code


# ---------------------------------------------------------------------------
# Java backend
# ---------------------------------------------------------------------------

class TestJavaBackend:
    def test_if_else(self):
        prog = _prog([
            If(Binary(BinOp.GT, Var("x"), IntLiteral(0)),
               then_block=Block([Return(IntLiteral(1))]),
               else_block=Block([Return(IntLiteral(0))]))
        ], params=[Param("x", IntType)], ret=IntType)
        code = JavaBackend().generate(prog)
        assert "if ((x > 0))" in code
        assert "return 1;" in code
        assert "} else {" in code
        assert "return 0;" in code

    def test_while(self):
        prog = _prog([
            While(Binary(BinOp.LT, Var("i"), IntLiteral(10)),
                  body=Block([Assign(Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1)))]))
        ])
        code = JavaBackend().generate(prog)
        assert "while ((i < 10))" in code
        assert "i = (i + 1);" in code

    def test_let_declaration(self):
        prog = _prog([Let("x", IntType, IntLiteral(42))])
        code = JavaBackend().generate(prog)
        assert "int x = 42;" in code

    def test_assign(self):
        prog = _prog([Assign(Var("x"), IntLiteral(99))])
        code = JavaBackend().generate(prog)
        assert "x = 99;" in code

    def test_null_literal(self):
        prog = _prog([Return(NullLiteral())])
        code = JavaBackend().generate(prog)
        assert "return null;" in code

    def test_bool_literals(self):
        prog = _prog([Return(BoolLiteral(True))])
        code = JavaBackend().generate(prog)
        assert "return true;" in code

    def test_string_literal(self):
        prog = _prog([Return(StringLiteral("hello"))])
        code = JavaBackend().generate(prog)
        assert 'return "hello";' in code

    def test_float_literal(self):
        prog = _prog([Return(FloatLiteral(1.5))])
        code = JavaBackend().generate(prog)
        assert "1.5" in code

    def test_call(self):
        prog = _prog([ExprStmt(Call(Var("add"), [IntLiteral(1), IntLiteral(2)]))])
        code = JavaBackend().generate(prog)
        assert "add(1, 2);" in code

    def test_print_call_mapped(self):
        prog = _prog([ExprStmt(Call(Var("print"), [StringLiteral("hi")]))])
        code = JavaBackend().generate(prog)
        assert "System.out.println" in code

    def test_field_access(self):
        prog = _prog([Return(FieldAccess(Var("p"), "x"))])
        code = JavaBackend().generate(prog)
        assert "p.x" in code

    def test_class_wrapper(self):
        prog = _prog([Return()])
        code = JavaBackend().generate(prog)
        assert "public class Main {" in code

    def test_main_function_signature(self):
        prog = _prog([Return()], name="main")
        code = JavaBackend().generate(prog)
        assert "public static void main(String[] args)" in code

    def test_void_return(self):
        prog = _prog([Return()])
        code = JavaBackend().generate(prog)
        assert "return;" in code

    def test_type_mapping(self):
        b = JavaBackend()
        assert b._type_to_str(IntType) == "int"
        assert b._type_to_str(FloatType) == "double"
        assert b._type_to_str(BoolType) == "boolean"
        assert b._type_to_str(StringType) == "String"
        assert b._type_to_str(VoidType) == "void"
        assert b._type_to_str(StructType("Foo")) == "Foo"
        assert b._type_to_str(AnyType) == "Object"

    def test_expr_statement(self):
        prog = _prog([ExprStmt(Var("x"))])
        code = JavaBackend().generate(prog)
        assert "x;" in code


# ---------------------------------------------------------------------------
# JS backend
# ---------------------------------------------------------------------------

class TestJSBackend:
    def test_if_else(self):
        prog = _prog([
            If(Binary(BinOp.GT, Var("x"), IntLiteral(0)),
               then_block=Block([Return(IntLiteral(1))]),
               else_block=Block([Return(IntLiteral(0))]))
        ], params=[Param("x", IntType)])
        code = JSBackend().generate(prog)
        assert "if ((x > 0))" in code
        assert "return 1;" in code
        assert "} else {" in code
        assert "return 0;" in code

    def test_while(self):
        prog = _prog([
            While(Binary(BinOp.LT, Var("i"), IntLiteral(10)),
                  body=Block([Assign(Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1)))]))
        ])
        code = JSBackend().generate(prog)
        assert "while ((i < 10))" in code
        assert "i = (i + 1);" in code

    def test_let_declaration(self):
        prog = _prog([Let("x", IntType, IntLiteral(42))])
        code = JSBackend().generate(prog)
        assert "let x = 42;" in code

    def test_assign(self):
        prog = _prog([Assign(Var("x"), IntLiteral(99))])
        code = JSBackend().generate(prog)
        assert "x = 99;" in code

    def test_null_literal(self):
        prog = _prog([Return(NullLiteral())])
        code = JSBackend().generate(prog)
        assert "return null;" in code

    def test_bool_literals(self):
        prog = _prog([Return(BoolLiteral(False))])
        code = JSBackend().generate(prog)
        assert "return false;" in code

    def test_string_literal(self):
        prog = _prog([Return(StringLiteral("world"))])
        code = JSBackend().generate(prog)
        assert '"world"' in code

    def test_float_literal(self):
        prog = _prog([Return(FloatLiteral(9.81))])
        code = JSBackend().generate(prog)
        assert "9.81" in code

    def test_eq_uses_strict_equality(self):
        prog = _prog([Return(Binary(BinOp.EQ, Var("a"), Var("b")))])
        code = JSBackend().generate(prog)
        assert "===" in code

    def test_neq_uses_strict_inequality(self):
        prog = _prog([Return(Binary(BinOp.NEQ, Var("a"), Var("b")))])
        code = JSBackend().generate(prog)
        assert "!==" in code

    def test_call(self):
        prog = _prog([ExprStmt(Call(Var("add"), [IntLiteral(1), IntLiteral(2)]))])
        code = JSBackend().generate(prog)
        assert "add(1, 2);" in code

    def test_print_call_mapped(self):
        prog = _prog([ExprStmt(Call(Var("print"), [StringLiteral("hi")]))])
        code = JSBackend().generate(prog)
        assert "console.log" in code

    def test_field_access(self):
        prog = _prog([Return(FieldAccess(Var("obj"), "name"))])
        code = JSBackend().generate(prog)
        assert "obj.name" in code

    def test_struct_as_class(self):
        prog = Program(structs=[Struct("Point", [("x", IntType), ("y", FloatType)])])
        code = JSBackend().generate(prog)
        assert "class Point" in code
        assert "constructor(x, y)" in code
        assert "this.x = x;" in code
        assert "this.y = y;" in code

    def test_void_return(self):
        prog = _prog([Return()])
        code = JSBackend().generate(prog)
        assert "return;" in code

    def test_expr_statement(self):
        prog = _prog([ExprStmt(Var("x"))])
        code = JSBackend().generate(prog)
        assert "x;" in code
