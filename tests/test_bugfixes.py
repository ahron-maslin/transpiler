"""Regression tests for the correctness-gap audit fixes.

Each test targets a specific bug that was silently wrong (or crashed) before
the fix: see CLAUDE.md's "Known state" section for the full list.
"""

import pytest

from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.frontend.python.parser import PythonFrontend
from transpiler.frontend.go.parser import GoFrontend
from transpiler.frontend.c.parser import CFrontend
from transpiler.frontend.java.parser import JavaFrontend
from transpiler.frontend.javascript.parser import JSFrontend
from transpiler.frontend.rust.parser import RustFrontend
from transpiler.backend.python.codegen import PythonBackend
from transpiler.backend.go.codegen import GoBackend
from transpiler.backend.java.codegen import JavaBackend
from transpiler.backend.c.codegen import CBackend
from transpiler.backend.javascript.codegen import JSBackend
from transpiler.backend.rust.codegen import RustBackend


class TestPythonBackendAndOr:
    def test_and_or_emit_python_keywords_not_symbols(self):
        expr = Binary(BinOp.AND, Var("a"), Binary(BinOp.OR, Var("b"), Var("c")))
        code = PythonBackend()._generate_expr(expr)
        assert "&&" not in code and "||" not in code
        assert " and " in code and " or " in code


class TestStringEscaping:
    @pytest.mark.parametrize(
        "backend_cls", [PythonBackend, GoBackend, JavaBackend, CBackend, JSBackend, RustBackend]
    )
    def test_quotes_and_backslashes_are_escaped(self, backend_cls):
        node = StringLiteral('has "quotes" and \\backslash')
        code = backend_cls()._generate_expr(node)
        assert '\\"quotes\\"' in code
        assert "\\\\backslash" in code


class TestGoIdentifierExport:
    def test_field_export_preserves_internal_casing(self):
        struct = Struct(name="User", fields=[("userID", IntType)])
        code = GoBackend()._generate_struct(struct)
        assert "UserID" in code
        assert "Userid" not in code


class TestJavaMainAndStructs:
    def test_main_with_params_is_not_clobbered(self):
        func = Function(
            name="main",
            params=[Param("x", IntType)],
            return_type=IntType,
            body=Block([Return(Var("x"))]),
        )
        code = JavaBackend().generate(Program(functions=[func]))
        assert "int x" in code
        assert "return x;" in code

    def test_structs_are_emitted(self):
        struct = Struct(name="Point", fields=[("x", IntType), ("y", IntType)])
        code = JavaBackend().generate(Program(structs=[struct]))
        assert "class Point" in code
        assert "public int x;" in code


class TestCPrintDispatch:
    @pytest.mark.parametrize(
        "arg,expected",
        [
            (StringLiteral("hi"), "print_str"),
            (FloatLiteral(1.5), "print_float"),
            (BoolLiteral(True), "print_bool"),
            (IntLiteral(1), "print_int"),
        ],
    )
    def test_print_dispatches_on_literal_type(self, arg, expected):
        call = Call(function=Var("print"), args=[arg])
        code = CBackend()._generate_expr(call)
        assert code.startswith(expected)

    def test_print_dispatches_on_declared_variable_type(self):
        backend = CBackend()
        func = Function(
            name="f",
            params=[Param("s", StringType)],
            return_type=VoidType,
            body=Block([ExprStmt(Call(function=Var("print"), args=[Var("s")]))]),
        )
        code = backend._generate_function(func)
        assert "print_str(s)" in code


class TestBackendNewNodeTypes:
    """For/Break/Continue/Cast/StructInit/ArrayInit/MapInit/IndexAccess/Unary used to
    silently render as empty strings in every backend."""

    def _program(self):
        struct = Struct(name="Point", fields=[("x", IntType), ("y", IntType)])
        func = Function(
            name="f",
            params=[Param("n", IntType)],
            return_type=IntType,
            body=Block(
                [
                    Let("total", IntType, IntLiteral(0)),
                    For(
                        init=Let("i", IntType, IntLiteral(0)),
                        condition=Binary(BinOp.LT, Var("i"), Var("n")),
                        update=Assign(Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1))),
                        body=Block(
                            [
                                If(
                                    Binary(BinOp.EQ, Var("i"), IntLiteral(3)),
                                    Block([Break()]),
                                ),
                                If(
                                    Binary(BinOp.EQ, Var("i"), IntLiteral(1)),
                                    Block([Continue()]),
                                ),
                            ]
                        ),
                    ),
                    Let("arr", AnyType, ArrayInit([IntLiteral(1), IntLiteral(2)])),
                    Let("idx", IntType, IndexAccess(Var("arr"), IntLiteral(0))),
                    Let("neg", IntType, Unary(UnOp.NEG, Var("total"))),
                    Let("notb", BoolType, Unary(UnOp.NOT, BoolLiteral(True))),
                    Let("casted", FloatType, Cast(Var("total"), FloatType)),
                    Let(
                        "p",
                        StructType("Point"),
                        StructInit("Point", {"x": IntLiteral(1), "y": IntLiteral(2)}),
                    ),
                    Return(Var("total")),
                ]
            ),
        )
        return Program(functions=[func], structs=[struct])

    @pytest.mark.parametrize(
        "backend_cls", [PythonBackend, GoBackend, JavaBackend, CBackend, JSBackend, RustBackend]
    )
    def test_generates_nonempty_output_without_crashing(self, backend_cls):
        code = backend_cls().generate(self._program())
        assert "for" in code or "while" in code
        assert "break" in code
        assert "continue" in code


class TestGoForLoopParsing:
    def test_c_style_for_loop_preserves_init_and_update(self):
        src = """
        package main
        func f(n int) int {
            total := 0
            for i := 0; i < n; i++ {
                total = total + i
            }
            return total
        }
        """
        prog = GoFrontend().parse(src)
        for_stmt = prog.functions[0].body.statements[1]
        assert isinstance(for_stmt, For)
        assert isinstance(for_stmt.init, Let)
        assert isinstance(for_stmt.update, Assign)

    def test_while_style_for_loop_condition_is_not_silently_true(self):
        # Before the fix, `for cond { ... }` always produced While(True, ...)
        # because child_by_field_name("condition") returned None for this shape.
        src = """
        package main
        func f(x int) int {
            for x < 5 {
                x = x + 1
            }
            return x
        }
        """
        prog = GoFrontend().parse(src)
        while_stmt = prog.functions[0].body.statements[0]
        assert isinstance(while_stmt, While)
        assert isinstance(while_stmt.condition, Binary)
        assert not (
            isinstance(while_stmt.condition, BoolLiteral) and while_stmt.condition.value is True
        )


class TestGoMultiAssign:
    def test_swap_uses_simultaneous_semantics(self):
        src = """
        package main
        func f() int {
            a := 1
            b := 2
            a, b = b, a
            return a
        }
        """
        prog = GoFrontend().parse(src)
        code = PythonBackend().generate(prog)
        ns = {}
        exec(code, ns)
        assert ns["f"]() == 2


class TestReservedWordEscaping:
    def test_python_keyword_identifier_is_renamed(self):
        func = Function(name="class", params=[], return_type=VoidType, body=Block())
        code = PythonBackend().generate(Program(functions=[func]))
        assert "def class_(" in code

    def test_rust_keyword_identifier_is_renamed(self):
        func = Function(name="type", params=[], return_type=VoidType, body=Block())
        code = RustBackend().generate(Program(functions=[func]))
        assert "fn type_(" in code


class TestPythonFrontendControlFlow:
    def test_for_range_desugars_to_ir_for(self):
        prog = PythonFrontend().parse(
            """
def f():
    total = 0
    for i in range(5):
        total += i
    return total
"""
        )
        code = PythonBackend().generate(prog)
        ns = {}
        exec(code, ns)
        assert ns["f"]() == 10

    def test_for_over_arbitrary_iterable_raises(self):
        with pytest.raises(NotImplementedError):
            PythonFrontend().parse(
                """
def f():
    for x in some_list:
        pass
"""
            )

    def test_multi_target_assign_produces_two_assigns(self):
        prog = PythonFrontend().parse(
            """
def f():
    a = b = 3
    return a + b
"""
        )
        code = PythonBackend().generate(prog)
        ns = {}
        exec(code, ns)
        assert ns["f"]() == 6

    def test_try_except_raises_instead_of_silently_dropping(self):
        with pytest.raises(NotImplementedError):
            PythonFrontend().parse(
                """
def f():
    try:
        pass
    except Exception:
        pass
"""
            )

    def test_with_statement_raises_instead_of_silently_dropping(self):
        with pytest.raises(NotImplementedError):
            PythonFrontend().parse(
                """
def f():
    with open("x") as fh:
        pass
"""
            )

    def test_module_level_globals_are_captured(self):
        prog = PythonFrontend().parse("count: int = 0\n")
        assert len(prog.globals) == 1
        assert prog.globals[0].name == "count"


class TestFunctionCallParsing:
    """Before the fix, none of C/Go/Java/JS ever parsed a call expression at
    all -- `print(x)` silently became NullLiteral in every one of them."""

    def test_c_call_is_parsed(self):
        prog = CFrontend().parse("int f() { print(1); return 0; }")
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, ExprStmt)
        assert isinstance(stmt.expr, Call)
        assert stmt.expr.function.name == "print"

    def test_go_call_is_parsed(self):
        prog = GoFrontend().parse("package main\nfunc f() { fmt.Println(1) }")
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, ExprStmt)
        assert isinstance(stmt.expr, Call)
        assert isinstance(stmt.expr.function, FieldAccess)

    def test_java_call_is_parsed(self):
        prog = JavaFrontend().parse("class C { void f() { System.out.println(1); } }")
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, ExprStmt)
        assert isinstance(stmt.expr, Call)

    def test_js_call_is_parsed(self):
        prog = JSFrontend().parse("function f() { console.log(1); }")
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, ExprStmt)
        assert isinstance(stmt.expr, Call)


class TestRustControlFlow:
    """Before the fix, `if`, `while`, and `loop` were entirely unhandled in the
    Rust frontend and silently became NullLiteral (a no-op)."""

    def test_while_loop_is_parsed(self):
        prog = RustFrontend().parse(
            "fn f() -> i32 { let mut x: i32 = 0; while x < 5 { x = x + 1; } x }"
        )
        stmts = prog.functions[0].body.statements
        assert any(isinstance(s, While) for s in stmts)

    def test_if_else_inside_loop_is_parsed(self):
        src = """
        fn f() -> i32 {
            let mut x: i32 = 0;
            loop {
                x = x + 1;
                if x == 3 {
                    break;
                }
            }
            x
        }
        """
        prog = RustFrontend().parse(src)
        code = PythonBackend().generate(prog)
        ns = {}
        exec(code, ns)
        # The while-body must contain a real If/Break, not a no-op, or this loops forever.
        assert "if" in code
        assert "break" in code

    def test_range_for_loop_desugars_to_ir_for(self):
        prog = RustFrontend().parse(
            "fn f() -> i32 { let mut total: i32 = 0; for i in 0..5 { total = total + i; } total }"
        )
        stmts = prog.functions[0].body.statements
        assert any(isinstance(s, For) for s in stmts)


class TestCliSurfacesErrors:
    def test_unsupported_construct_exits_nonzero_not_silently(self, tmp_path, capsys):
        import sys
        from unittest.mock import patch
        from transpiler.cli.main import main

        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def f():\n    try:\n        pass\n    except Exception:\n        pass\n"
        )

        with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "python"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

        out, err = capsys.readouterr()
        assert "NotImplementedError" in err
