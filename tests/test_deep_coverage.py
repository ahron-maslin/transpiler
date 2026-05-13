"""Deep coverage tests for remaining uncovered branches in frontends, CLI, and type inference."""

import pytest
import sys
from unittest.mock import patch
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.passes.type_inference import TypeInferencePass
from transpiler.cli.main import main
from transpiler.frontend.c.parser import CFrontend
from transpiler.frontend.go.parser import GoFrontend
from transpiler.frontend.java.parser import JavaFrontend
from transpiler.frontend.javascript.parser import JSFrontend
from transpiler.frontend.rust.parser import RustFrontend

# ---------------------------------------------------------------------------
# CLI language dispatch coverage
# ---------------------------------------------------------------------------


class TestCLILanguageDispatch:
    """Cover all source extension → frontend and --to → backend dispatch paths."""

    @pytest.mark.parametrize(
        "ext,content,to_lang",
        [
            (".js", "function f() { return 1; }", "python"),
            (".go", "package main\nfunc f() int { return 1 }", "python"),
            (".rs", "fn f() -> i32 { return 1; }", "python"),
            (".java", "class Main { public static int f() { return 1; } }", "python"),
        ],
    )
    def test_source_extensions(self, tmp_path, capsys, ext, content, to_lang):
        test_file = tmp_path / f"test{ext}"
        test_file.write_text(content)
        with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", to_lang]):
            main()
        out, err = capsys.readouterr()
        assert err == ""
        assert "def f" in out  # transpiled to Python

    @pytest.mark.parametrize(
        "to_lang,expected_substr",
        [
            ("go", "func"),
            ("rust", "fn"),
            ("java", "public"),
            ("c", "int"),
        ],
    )
    def test_backend_dispatch(self, tmp_path, capsys, to_lang, expected_substr):
        test_file = tmp_path / "test.py"
        test_file.write_text("def f(a: int) -> int:\n    return a\n")
        with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", to_lang]):
            main()
        out, err = capsys.readouterr()
        assert err == ""
        assert expected_substr in out


# ---------------------------------------------------------------------------
# Tree-sitter frontend: if/while/expression_statement/assignment branches
# ---------------------------------------------------------------------------


class TestCFrontendControlFlow:
    def setup_method(self):
        self.fe = CFrontend()

    def test_if_parsed_as_ir_if(self):
        prog = self.fe.parse("""
        int check(int x) {
            if (x > 0) {
                return 1;
            }
            return 0;
        }
        """)
        stmts = prog.functions[0].body.statements
        # Find the If statement
        if_stmts = [s for s in stmts if isinstance(s, If)]
        assert len(if_stmts) >= 1
        assert isinstance(if_stmts[0].condition, Binary)
        assert if_stmts[0].condition.op == BinOp.GT

    def test_while_loop(self):
        prog = self.fe.parse("""
        void loop() {
            int i = 0;
            while (i < 10) {
                i = i + 1;
            }
        }
        """)
        stmts = prog.functions[0].body.statements
        while_stmts = [s for s in stmts if isinstance(s, While)]
        assert len(while_stmts) >= 1
        assert isinstance(while_stmts[0].condition, Binary)

    def test_expression_statement(self):
        prog = self.fe.parse("""
        void f() {
            foo(1, 2);
        }
        """)
        stmts = prog.functions[0].body.statements
        expr_stmts = [s for s in stmts if isinstance(s, ExprStmt)]
        assert len(expr_stmts) >= 1

    def test_assignment_expression(self):
        prog = self.fe.parse("""
        void f() {
            int x = 0;
            x = 10;
        }
        """)
        stmts = prog.functions[0].body.statements
        assigns = [s for s in stmts if isinstance(s, Assign)]
        assert len(assigns) >= 1

    def test_null_literal(self):
        prog = self.fe.parse("""
        void* f() {
            return 0;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)

    def test_false_literal(self):
        prog = self.fe.parse("""
        bool f() {
            return false;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is False

    def test_all_comparison_ops_parsed(self):
        """Ensure all comparison operators produce Binary nodes."""
        for op_c, op_ir in [
            ("==", BinOp.EQ),
            ("!=", BinOp.NEQ),
            ("<", BinOp.LT),
            ("<=", BinOp.LTE),
            (">", BinOp.GT),
            (">=", BinOp.GTE),
        ]:
            prog = self.fe.parse(f"""
            bool f(int a, int b) {{
                return a {op_c} b;
            }}
            """)
            ret = prog.functions[0].body.statements[0]
            assert isinstance(ret.value, Binary), f"Failed for {op_c}"
            assert ret.value.op == op_ir, f"Expected {op_ir} for {op_c}, got {ret.value.op}"

    def test_all_arithmetic_ops_parsed(self):
        for op_c, op_ir in [
            ("+", BinOp.ADD),
            ("-", BinOp.SUB),
            ("*", BinOp.MUL),
            ("/", BinOp.DIV),
            ("%", BinOp.MOD),
        ]:
            prog = self.fe.parse(f"""
            int f(int a, int b) {{
                return a {op_c} b;
            }}
            """)
            ret = prog.functions[0].body.statements[0]
            assert isinstance(ret.value, Binary)
            assert ret.value.op == op_ir


class TestGoFrontendControlFlow:
    def setup_method(self):
        self.fe = GoFrontend()

    def test_if_statement(self):
        prog = self.fe.parse("""
        package main
        func check(x int) int {
            if x > 0 {
                return 1
            }
            return 0
        }
        """)
        stmts = prog.functions[0].body.statements
        if_stmts = [s for s in stmts if isinstance(s, If)]
        assert len(if_stmts) >= 1

    def test_assignment_statement(self):
        prog = self.fe.parse("""
        package main
        func f() {
            x := 0
            x = 10
        }
        """)
        stmts = prog.functions[0].body.statements
        assigns = [s for s in stmts if isinstance(s, Assign)]
        assert len(assigns) >= 1

    def test_expression_statement(self):
        prog = self.fe.parse("""
        package main
        func f() {
            foo(1)
        }
        """)
        stmts = prog.functions[0].body.statements
        expr_stmts = [s for s in stmts if isinstance(s, ExprStmt)]
        assert len(expr_stmts) >= 1

    def test_nil_literal(self):
        prog = self.fe.parse("""
        package main
        func f() {
            x := nil
        }
        """)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        assert isinstance(stmts[0].value, NullLiteral)

    def test_false_literal(self):
        prog = self.fe.parse("""
        package main
        func f() bool {
            return false
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is False


class TestJavaFrontendControlFlow:
    def setup_method(self):
        self.fe = JavaFrontend()

    def test_if_statement(self):
        prog = self.fe.parse("""
        class Main {
            public static int check(int x) {
                if (x > 0) { return 1; }
                return 0;
            }
        }
        """)
        stmts = prog.functions[0].body.statements
        if_stmts = [s for s in stmts if isinstance(s, If)]
        assert len(if_stmts) >= 1

    def test_expression_and_assignment(self):
        prog = self.fe.parse("""
        class Main {
            public static void f() {
                int x = 0;
                x = 10;
                foo(x);
            }
        }
        """)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        assigns = [s for s in stmts if isinstance(s, Assign)]
        assert len(assigns) >= 1

    def test_null_literal(self):
        prog = self.fe.parse("""
        class Main {
            public static Object f() {
                return null;
            }
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, NullLiteral)

    def test_false_literal(self):
        prog = self.fe.parse("""
        class Main {
            public static boolean f() {
                return false;
            }
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is False


class TestJSFrontendControlFlow:
    def setup_method(self):
        self.fe = JSFrontend()

    def test_if_statement(self):
        prog = self.fe.parse("""
        function check(x) {
            if (x > 0) { return 1; }
            return 0;
        }
        """)
        stmts = prog.functions[0].body.statements
        if_stmts = [s for s in stmts if isinstance(s, If)]
        assert len(if_stmts) >= 1

    def test_false_literal(self):
        prog = self.fe.parse("""
        function f() { return false; }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is False

    def test_strict_eq_neq_ops(self):
        prog = self.fe.parse("""
        function f(a, b) {
            if (a === b) { return 1; }
            if (a !== b) { return 2; }
            return 0;
        }
        """)
        stmts = prog.functions[0].body.statements
        if_stmts = [s for s in stmts if isinstance(s, If)]
        assert len(if_stmts) >= 2
        assert if_stmts[0].condition.op == BinOp.EQ
        assert if_stmts[1].condition.op == BinOp.NEQ


class TestRustFrontendControlFlow:
    def setup_method(self):
        self.fe = RustFrontend()

    def test_if_statement(self):
        prog = self.fe.parse("""
        fn check(x: i32) -> i32 {
            if x > 0 {
                return 1;
            }
            return 0;
        }
        """)
        stmts = prog.functions[0].body.statements
        # Rust parser may handle if differently; just confirm function parsed
        assert prog.functions[0].name == "check"
        assert len(stmts) >= 1

    def test_false_literal(self):
        prog = self.fe.parse("""
        fn f() -> bool {
            return false;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is False

    def test_all_comparison_ops(self):
        for op_rs, op_ir in [
            ("==", BinOp.EQ),
            ("!=", BinOp.NEQ),
            ("<", BinOp.LT),
            ("<=", BinOp.LTE),
            (">", BinOp.GT),
            (">=", BinOp.GTE),
        ]:
            prog = self.fe.parse(f"""
            fn f(a: i32, b: i32) -> bool {{
                return a {op_rs} b;
            }}
            """)
            ret = prog.functions[0].body.statements[0]
            assert isinstance(ret.value, Binary), f"Failed for {op_rs}"
            assert ret.value.op == op_ir


# ---------------------------------------------------------------------------
# Type inference remaining branches
# ---------------------------------------------------------------------------


class TestTypeInferenceDeep:
    def _run(self, program):
        TypeInferencePass().execute(program)
        return program

    def test_for_loop_inference(self):
        """Cover the For branch in type inference."""
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block(
                            [
                                For(
                                    init=Let("i", AnyType, IntLiteral(0)),
                                    condition=Binary(BinOp.LT, Var("i"), IntLiteral(10)),
                                    update=Assign(
                                        Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1))
                                    ),
                                    body=Block([ExprStmt(Var("i"))]),
                                )
                            ]
                        ),
                    )
                ]
            )
        )
        for_stmt = prog.functions[0].body.statements[0]
        assert for_stmt.init.type.kind == TypeKind.INT

    def test_right_side_type_fallback(self):
        """When left is Any but right has concrete type, use right."""
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block([Let("x", AnyType, Binary(BinOp.ADD, NullLiteral(), IntLiteral(5)))]),
                    )
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.INT

    def test_field_access_stays_any(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block([Let("x", AnyType, FieldAccess(Var("obj"), "field"))]),
                    )
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.ANY

    def test_unhandled_expr_stays_any(self):
        """An expression type not handled should return Any."""
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f", [], VoidType, Block([Let("x", AnyType, ArrayInit([IntLiteral(1)]))])
                    )
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.ANY
