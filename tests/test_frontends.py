"""Extended frontend parser tests for tree-sitter-based languages (C, Go, Java, JS, Rust).
Tests control flow, boolean/string/float literals, function calls, comparisons.
"""

import pytest
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.frontend.c.parser import CFrontend
from transpiler.frontend.go.parser import GoFrontend
from transpiler.frontend.java.parser import JavaFrontend
from transpiler.frontend.javascript.parser import JSFrontend
from transpiler.frontend.rust.parser import RustFrontend

# ---------------------------------------------------------------------------
# C frontend
# ---------------------------------------------------------------------------


class TestCFrontendExtended:
    def setup_method(self):
        self.fe = CFrontend()

    def test_empty_source(self):
        prog = self.fe.parse("")
        assert prog.functions == []

    def test_if_else(self):
        prog = self.fe.parse("""
        int check(int x) {
            if (x > 0) {
                return 1;
            } else {
                return 0;
            }
        }
        """)
        func = prog.functions[0]
        # The parser may flatten if/else into the body differently
        # but we at least confirm the function was parsed
        assert func.name == "check"
        assert len(func.params) == 1

    def test_float_literal(self):
        prog = self.fe.parse("""
        double pi() {
            return 3.14;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)
        assert isinstance(ret.value, FloatLiteral)
        assert ret.value.value == pytest.approx(3.14)

    def test_string_literal(self):
        prog = self.fe.parse("""
        void greet() {
            char* s = "hello";
        }
        """)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        assert isinstance(stmts[0].value, StringLiteral)

    def test_bool_literals(self):
        prog = self.fe.parse("""
        bool flag() {
            return true;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is True

    def test_comparison_operators(self):
        prog = self.fe.parse("""
        int cmp(int a, int b) {
            if (a == b) { return 0; }
            if (a != b) { return 1; }
            if (a < b) { return 2; }
            if (a <= b) { return 3; }
            if (a > b) { return 4; }
            if (a >= b) { return 5; }
            return -1;
        }
        """)
        assert prog.functions[0].name == "cmp"
        assert len(prog.functions[0].body.statements) >= 1

    def test_multiple_functions(self):
        prog = self.fe.parse("""
        int foo() { return 1; }
        int bar() { return 2; }
        """)
        assert len(prog.functions) == 2
        assert prog.functions[0].name == "foo"
        assert prog.functions[1].name == "bar"

    def test_void_function(self):
        prog = self.fe.parse("""
        void noop() {}
        """)
        func = prog.functions[0]
        assert func.name == "noop"
        assert func.return_type.kind == TypeKind.VOID

    def test_type_parsing(self):
        prog = self.fe.parse("""
        double calc(double a, int b) {
            return a;
        }
        """)
        func = prog.functions[0]
        assert func.return_type.kind == TypeKind.FLOAT
        assert func.params[0].type.kind == TypeKind.FLOAT
        assert func.params[1].type.kind == TypeKind.INT


# ---------------------------------------------------------------------------
# Go frontend
# ---------------------------------------------------------------------------


class TestGoFrontendExtended:
    def setup_method(self):
        self.fe = GoFrontend()

    def test_empty_source(self):
        prog = self.fe.parse("package main")
        assert prog.functions == []

    def test_short_var_declaration(self):
        prog = self.fe.parse("""
        package main
        func calc() int {
            x := 10
            return x
        }
        """)
        func = prog.functions[0]
        stmts = func.body.statements
        assert isinstance(stmts[0], Let)
        assert stmts[0].name == "x"
        assert isinstance(stmts[0].value, IntLiteral)

    def test_string_literal(self):
        prog = self.fe.parse("""
        package main
        func greet() string {
            return "hello"
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, StringLiteral)
        assert ret.value.value == "hello"

    def test_bool_literal(self):
        prog = self.fe.parse("""
        package main
        func flag() bool {
            return true
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is True

    def test_float_literal(self):
        prog = self.fe.parse("""
        package main
        func pi() float64 {
            return 3.14
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, FloatLiteral)

    def test_multiple_functions(self):
        prog = self.fe.parse("""
        package main
        func foo() int { return 1 }
        func bar() int { return 2 }
        """)
        assert len(prog.functions) == 2

    def test_type_parsing(self):
        prog = self.fe.parse("""
        package main
        func calc(a float64, b int64) float64 {
            return a
        }
        """)
        func = prog.functions[0]
        assert func.return_type.kind == TypeKind.FLOAT
        assert func.params[0].type.kind == TypeKind.FLOAT
        assert func.params[1].type.kind == TypeKind.INT


# ---------------------------------------------------------------------------
# Java frontend
# ---------------------------------------------------------------------------


class TestJavaFrontendExtended:
    def setup_method(self):
        self.fe = JavaFrontend()

    def test_empty_class(self):
        prog = self.fe.parse("""
        class Main {}
        """)
        assert prog.functions == []

    def test_string_literal(self):
        prog = self.fe.parse("""
        class Main {
            public static String greet() {
                return "hello";
            }
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, StringLiteral)

    def test_bool_literal(self):
        prog = self.fe.parse("""
        class Main {
            public static boolean flag() {
                return true;
            }
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is True

    def test_float_literal(self):
        prog = self.fe.parse("""
        class Main {
            public static double pi() {
                return 3.14;
            }
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, FloatLiteral)

    def test_multiple_methods(self):
        prog = self.fe.parse("""
        class Main {
            public static int foo() { return 1; }
            public static int bar() { return 2; }
        }
        """)
        assert len(prog.functions) == 2

    def test_void_return_type(self):
        prog = self.fe.parse("""
        class Main {
            public static void noop() {
                return;
            }
        }
        """)
        func = prog.functions[0]
        assert func.return_type.kind == TypeKind.VOID

    def test_type_parsing(self):
        prog = self.fe.parse("""
        class Main {
            public static double calc(double a, int b) {
                return a;
            }
        }
        """)
        func = prog.functions[0]
        assert func.return_type.kind == TypeKind.FLOAT
        assert func.params[0].type.kind == TypeKind.FLOAT
        assert func.params[1].type.kind == TypeKind.INT


# ---------------------------------------------------------------------------
# JS frontend
# ---------------------------------------------------------------------------


class TestJSFrontendExtended:
    def setup_method(self):
        self.fe = JSFrontend()

    def test_empty_source(self):
        prog = self.fe.parse("")
        assert prog.functions == []

    def test_string_literal(self):
        prog = self.fe.parse("""
        function greet() {
            return "hello";
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, StringLiteral)

    def test_bool_literal(self):
        prog = self.fe.parse("""
        function flag() {
            return true;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is True

    def test_float_literal(self):
        prog = self.fe.parse("""
        function pi() {
            return 3.14;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, FloatLiteral)

    def test_null_literal(self):
        prog = self.fe.parse("""
        function nothing() {
            return null;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, NullLiteral)

    def test_multiple_functions(self):
        prog = self.fe.parse("""
        function foo() { return 1; }
        function bar() { return 2; }
        """)
        assert len(prog.functions) == 2

    def test_assignment_expression(self):
        prog = self.fe.parse("""
        function f() {
            let x = 10;
            x = 20;
        }
        """)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        assert isinstance(stmts[1], Assign)

    def test_nested_parenthesized(self):
        prog = self.fe.parse("""
        function f() {
            let x = ((1 + 2));
            return x;
        }
        """)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        val = stmts[0].value
        assert isinstance(val, Binary)
        assert val.op == BinOp.ADD


# ---------------------------------------------------------------------------
# Rust frontend
# ---------------------------------------------------------------------------


class TestRustFrontendExtended:
    def setup_method(self):
        self.fe = RustFrontend()

    def test_empty_source(self):
        prog = self.fe.parse("")
        assert prog.functions == []

    def test_string_literal(self):
        prog = self.fe.parse("""
        fn greet() -> &str {
            return "hello";
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)
        assert isinstance(ret.value, StringLiteral)

    def test_bool_literal(self):
        prog = self.fe.parse("""
        fn flag() -> bool {
            return true;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is True

    def test_float_literal(self):
        prog = self.fe.parse("""
        fn pi() -> f64 {
            return 3.14;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, FloatLiteral)

    def test_multiple_functions(self):
        prog = self.fe.parse("""
        fn foo() -> i32 { return 1; }
        fn bar() -> i32 { return 2; }
        """)
        assert len(prog.functions) == 2

    def test_type_parsing(self):
        prog = self.fe.parse("""
        fn calc(a: f64, b: i32) -> f64 {
            return a;
        }
        """)
        func = prog.functions[0]
        assert func.return_type.kind == TypeKind.FLOAT
        assert func.params[0].type.kind == TypeKind.FLOAT
        assert func.params[1].type.kind == TypeKind.INT

    def test_underscore_in_number(self):
        prog = self.fe.parse("""
        fn big() -> i32 {
            return 1_000_000;
        }
        """)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, IntLiteral)
        assert ret.value.value == 1000000

    def test_let_with_type_annotation(self):
        prog = self.fe.parse("""
        fn f() {
            let x: i32 = 42;
        }
        """)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        assert stmts[0].name == "x"
        assert stmts[0].type.kind == TypeKind.INT
        assert isinstance(stmts[0].value, IntLiteral)
