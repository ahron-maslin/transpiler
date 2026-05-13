"""Edge case tests for parser frontends, backends, and IR invariants."""

import pytest
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.passes.type_inference import TypeInferencePass
from transpiler.frontend.python.parser import PythonFrontend
from transpiler.backend.python.codegen import PythonBackend
from transpiler.backend.c.codegen import CBackend
from transpiler.backend.javascript.codegen import JSBackend

# ---------------------------------------------------------------------------
# IR invariant tests
# ---------------------------------------------------------------------------


class TestIRNodeConstruction:
    """Verify IR nodes can be constructed and hold correct data."""

    def test_empty_program(self):
        p = Program()
        assert p.functions == []
        assert p.structs == []
        assert p.globals == []

    def test_empty_block(self):
        b = Block()
        assert b.statements == []

    def test_nested_binary_preserves_structure(self):
        """(a + b) * (c - d) should preserve full tree."""
        inner_left = Binary(BinOp.ADD, Var("a"), Var("b"))
        inner_right = Binary(BinOp.SUB, Var("c"), Var("d"))
        outer = Binary(BinOp.MUL, inner_left, inner_right)

        assert outer.op == BinOp.MUL
        assert outer.left.op == BinOp.ADD
        assert outer.right.op == BinOp.SUB
        assert outer.left.left.name == "a"
        assert outer.right.right.name == "d"

    def test_all_binop_values(self):
        """All BinOp enum members should have string values."""
        expected = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"}
        actual = {op.value for op in BinOp}
        assert actual == expected

    def test_all_typekind_values(self):
        """TypeKind enum should contain all expected kinds."""
        expected = {
            "Void",
            "Bool",
            "Int",
            "Float",
            "String",
            "Array",
            "Map",
            "Struct",
            "Function",
            "Optional",
            "Any",
        }
        actual = {tk.value for tk in TypeKind}
        assert actual == expected

    def test_primitive_type_singletons(self):
        """Primitive type singletons should have correct kinds."""
        assert IntType.kind == TypeKind.INT
        assert FloatType.kind == TypeKind.FLOAT
        assert BoolType.kind == TypeKind.BOOL
        assert StringType.kind == TypeKind.STRING
        assert VoidType.kind == TypeKind.VOID
        assert AnyType.kind == TypeKind.ANY

    def test_composite_types(self):
        arr = ArrayType(IntType)
        assert arr.kind == TypeKind.ARRAY
        assert arr.element_type.kind == TypeKind.INT

        m = MapType(StringType, IntType)
        assert m.kind == TypeKind.MAP
        assert m.key_type.kind == TypeKind.STRING

        st = StructType("Point")
        assert st.kind == TypeKind.STRUCT
        assert st.name == "Point"

        ft = FunctionType([IntType, IntType], BoolType)
        assert ft.kind == TypeKind.FUNCTION
        assert len(ft.params) == 2
        assert ft.return_type.kind == TypeKind.BOOL

        opt = OptionalType(StringType)
        assert opt.kind == TypeKind.OPTIONAL
        assert opt.inner_type.kind == TypeKind.STRING

    def test_function_with_no_params(self):
        f = Function(name="noop", params=[], return_type=VoidType, body=Block([Return()]))
        assert f.name == "noop"
        assert f.params == []
        assert f.body.statements[0].value is None

    def test_if_without_else(self):
        stmt = If(condition=BoolLiteral(True), then_block=Block([Return(IntLiteral(1))]))
        assert stmt.else_block is None

    def test_if_with_else(self):
        stmt = If(
            condition=BoolLiteral(True),
            then_block=Block([Return(IntLiteral(1))]),
            else_block=Block([Return(IntLiteral(0))]),
        )
        assert stmt.else_block is not None
        assert len(stmt.else_block.statements) == 1


# ---------------------------------------------------------------------------
# Type inference edge cases
# ---------------------------------------------------------------------------


class TestTypeInference:
    def _run(self, program):
        TypeInferencePass().execute(program)
        return program

    def test_comparison_returns_bool(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [Param("x", IntType)],
                        VoidType,
                        Block([Let("r", AnyType, Binary(BinOp.LT, Var("x"), IntLiteral(10)))]),
                    )
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.BOOL

    def test_logical_and_returns_bool(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block(
                            [
                                Let(
                                    "r",
                                    AnyType,
                                    Binary(BinOp.AND, BoolLiteral(True), BoolLiteral(False)),
                                )
                            ]
                        ),
                    )
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.BOOL

    def test_float_literal_inferred(self):
        prog = self._run(
            Program(
                functions=[
                    Function("f", [], VoidType, Block([Let("x", AnyType, FloatLiteral(3.14))]))
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.FLOAT

    def test_string_literal_inferred(self):
        prog = self._run(
            Program(
                functions=[
                    Function("f", [], VoidType, Block([Let("s", AnyType, StringLiteral("hello"))]))
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.STRING

    def test_bool_literal_inferred(self):
        prog = self._run(
            Program(
                functions=[
                    Function("f", [], VoidType, Block([Let("b", AnyType, BoolLiteral(True))]))
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.BOOL

    def test_explicit_type_not_overridden(self):
        """If the Let already has a concrete type, inference should not change it."""
        prog = self._run(
            Program(
                functions=[
                    Function("f", [], VoidType, Block([Let("x", FloatType, IntLiteral(42))]))
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.FLOAT

    def test_chained_let_propagation(self):
        """let x = 10; let y = x + 1; => y should be Int."""
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block(
                            [
                                Let("x", AnyType, IntLiteral(10)),
                                Let("y", AnyType, Binary(BinOp.ADD, Var("x"), IntLiteral(1))),
                            ]
                        ),
                    )
                ]
            )
        )
        stmts = prog.functions[0].body.statements
        assert stmts[0].type.kind == TypeKind.INT
        assert stmts[1].type.kind == TypeKind.INT

    def test_null_literal_stays_any(self):
        prog = self._run(
            Program(
                functions=[Function("f", [], VoidType, Block([Let("n", AnyType, NullLiteral())]))]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.ANY

    def test_call_infers_return_type(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "add",
                        [Param("a", IntType), Param("b", IntType)],
                        IntType,
                        Block([Return(Binary(BinOp.ADD, Var("a"), Var("b")))]),
                    ),
                    Function(
                        "main",
                        [],
                        VoidType,
                        Block(
                            [Let("r", AnyType, Call(Var("add"), [IntLiteral(1), IntLiteral(2)]))]
                        ),
                    ),
                ]
            )
        )
        main_let = prog.functions[1].body.statements[0]
        assert main_let.type.kind == TypeKind.INT

    def test_unknown_function_call_stays_any(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f", [], VoidType, Block([Let("r", AnyType, Call(Var("unknown"), []))])
                    )
                ]
            )
        )
        assert prog.functions[0].body.statements[0].type.kind == TypeKind.ANY

    def test_inference_inside_if_block(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block(
                            [
                                If(
                                    BoolLiteral(True),
                                    then_block=Block([Let("x", AnyType, IntLiteral(5))]),
                                    else_block=Block([Let("y", AnyType, StringLiteral("hi"))]),
                                )
                            ]
                        ),
                    )
                ]
            )
        )
        if_stmt = prog.functions[0].body.statements[0]
        assert if_stmt.then_block.statements[0].type.kind == TypeKind.INT
        assert if_stmt.else_block.statements[0].type.kind == TypeKind.STRING

    def test_inference_inside_while_block(self):
        prog = self._run(
            Program(
                functions=[
                    Function(
                        "f",
                        [],
                        VoidType,
                        Block(
                            [
                                While(
                                    BoolLiteral(True),
                                    body=Block([Let("i", AnyType, IntLiteral(0))]),
                                )
                            ]
                        ),
                    )
                ]
            )
        )
        while_stmt = prog.functions[0].body.statements[0]
        assert while_stmt.body.statements[0].type.kind == TypeKind.INT


# ---------------------------------------------------------------------------
# Python frontend edge cases
# ---------------------------------------------------------------------------


class TestPythonFrontendEdgeCases:
    def setup_method(self):
        self.frontend = PythonFrontend()

    def test_empty_source(self):
        prog = self.frontend.parse("")
        assert prog.functions == []

    def test_whitespace_only(self):
        prog = self.frontend.parse("   \n\n   \n")
        assert prog.functions == []

    def test_if_else(self):
        code = """
def check(x: int) -> int:
    if x > 0:
        return 1
    else:
        return 0
"""
        prog = self.frontend.parse(code)
        func = prog.functions[0]
        if_stmt = func.body.statements[0]
        assert isinstance(if_stmt, If)
        assert isinstance(if_stmt.condition, Binary)
        assert if_stmt.condition.op == BinOp.GT
        assert if_stmt.else_block is not None

    def test_while_loop(self):
        code = """
def loop() -> int:
    i: int = 0
    while i < 10:
        i = i + 1
    return i
"""
        prog = self.frontend.parse(code)
        stmts = prog.functions[0].body.statements
        assert isinstance(stmts[0], Let)
        assert isinstance(stmts[1], While)
        assert isinstance(stmts[1].condition, Binary)
        assert stmts[1].condition.op == BinOp.LT

    def test_function_call(self):
        code = """
def caller():
    result = add(1, 2)
"""
        prog = self.frontend.parse(code)
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, Assign)
        assert isinstance(stmt.value, Call)
        assert isinstance(stmt.value.function, Var)
        assert stmt.value.function.name == "add"
        assert len(stmt.value.args) == 2

    def test_boolean_literal(self):
        code = """
def flag() -> bool:
    return True
"""
        prog = self.frontend.parse(code)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)
        assert isinstance(ret.value, BoolLiteral)
        assert ret.value.value is True

    def test_string_literal(self):
        code = """
def greet() -> str:
    return "hello"
"""
        prog = self.frontend.parse(code)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret.value, StringLiteral)
        assert ret.value.value == "hello"

    def test_none_literal(self):
        code = """
def nothing():
    x = None
"""
        prog = self.frontend.parse(code)
        stmt = prog.functions[0].body.statements[0]
        assert isinstance(stmt, Assign)
        assert isinstance(stmt.value, NullLiteral)

    def test_multiple_functions(self):
        code = """
def foo():
    return 1
def bar():
    return 2
def baz():
    return 3
"""
        prog = self.frontend.parse(code)
        assert len(prog.functions) == 3
        assert [f.name for f in prog.functions] == ["foo", "bar", "baz"]

    def test_comparison_operators(self):
        code = """
def cmp(a: int, b: int) -> bool:
    return a == b
"""
        prog = self.frontend.parse(code)
        ret = prog.functions[0].body.statements[0].value
        assert isinstance(ret, Binary)
        assert ret.op == BinOp.EQ

    @pytest.mark.parametrize(
        "op_str,expected_op",
        [
            ("a + b", BinOp.ADD),
            ("a - b", BinOp.SUB),
            ("a * b", BinOp.MUL),
            ("a / b", BinOp.DIV),
            ("a % b", BinOp.MOD),
        ],
    )
    def test_arithmetic_operators(self, op_str, expected_op):
        code = f"""
def f(a: int, b: int) -> int:
    return {op_str}
"""
        prog = self.frontend.parse(code)
        ret = prog.functions[0].body.statements[0].value
        assert isinstance(ret, Binary)
        assert ret.op == expected_op

    def test_field_access(self):
        code = """
def get_x(p):
    return p.x
"""
        prog = self.frontend.parse(code)
        ret = prog.functions[0].body.statements[0].value
        assert isinstance(ret, FieldAccess)
        assert ret.field == "x"

    def test_struct_class_parsed(self):
        code = """
class Point:
    x: int
    y: float
"""
        prog = self.frontend.parse(code)
        assert len(prog.structs) == 1
        s = prog.structs[0]
        assert s.name == "Point"
        assert len(s.fields) == 2
        assert s.fields[0] == ("x", IntType)
        assert s.fields[1][1].kind == TypeKind.FLOAT

    def test_void_return(self):
        code = """
def noop():
    return
"""
        prog = self.frontend.parse(code)
        ret = prog.functions[0].body.statements[0]
        assert isinstance(ret, Return)
        assert ret.value is None


# ---------------------------------------------------------------------------
# Backend codegen edge cases
# ---------------------------------------------------------------------------


class TestBackendEdgeCases:
    def _make_program(self, stmts, params=None, ret=VoidType):
        return Program(functions=[Function("test_fn", params or [], ret, Block(stmts))])

    def test_c_if_else_codegen(self):
        prog = self._make_program(
            [
                If(
                    Binary(BinOp.GT, Var("x"), IntLiteral(0)),
                    then_block=Block([Return(IntLiteral(1))]),
                    else_block=Block([Return(IntLiteral(0))]),
                )
            ],
            params=[Param("x", IntType)],
            ret=IntType,
        )
        code = CBackend().generate(prog)
        assert "if ((x > 0))" in code
        assert "return 1;" in code
        assert "else" in code
        assert "return 0;" in code

    def test_c_while_codegen(self):
        prog = self._make_program(
            [
                Let("i", IntType, IntLiteral(0)),
                While(
                    Binary(BinOp.LT, Var("i"), IntLiteral(10)),
                    body=Block([Assign(Var("i"), Binary(BinOp.ADD, Var("i"), IntLiteral(1)))]),
                ),
            ]
        )
        code = CBackend().generate(prog)
        assert "int i = 0;" in code
        assert "while ((i < 10))" in code
        assert "i = (i + 1);" in code

    def test_c_null_literal(self):
        prog = self._make_program([Return(NullLiteral())])
        code = CBackend().generate(prog)
        assert "return NULL;" in code

    def test_c_bool_literal(self):
        prog = self._make_program([Return(BoolLiteral(True))])
        code = CBackend().generate(prog)
        assert "return true;" in code

    def test_c_string_literal(self):
        prog = self._make_program([Return(StringLiteral("hello"))])
        code = CBackend().generate(prog)
        assert 'return "hello";' in code

    def test_js_if_else_codegen(self):
        prog = self._make_program(
            [
                If(
                    Binary(BinOp.GT, Var("x"), IntLiteral(0)),
                    then_block=Block([Return(IntLiteral(1))]),
                    else_block=Block([Return(IntLiteral(0))]),
                )
            ],
            params=[Param("x", IntType)],
        )
        code = JSBackend().generate(prog)
        assert "if ((x > 0))" in code
        assert "return 1;" in code
        assert "else" in code

    def test_python_if_else_codegen(self):
        prog = self._make_program(
            [
                If(
                    Binary(BinOp.GT, Var("x"), IntLiteral(0)),
                    then_block=Block([Return(IntLiteral(1))]),
                    else_block=Block([Return(IntLiteral(0))]),
                )
            ],
            params=[Param("x", IntType)],
        )
        code = PythonBackend().generate(prog)
        assert "if (x > 0):" in code
        assert "return 1" in code
        assert "else:" in code
        assert "return 0" in code

    def test_python_while_codegen(self):
        prog = self._make_program(
            [While(Binary(BinOp.LT, Var("i"), IntLiteral(10)), body=Block([ExprStmt(Var("i"))]))]
        )
        code = PythonBackend().generate(prog)
        assert "while (i < 10):" in code

    def test_python_none_literal(self):
        prog = self._make_program([Return(NullLiteral())])
        code = PythonBackend().generate(prog)
        assert "return None" in code

    def test_python_empty_function_body(self):
        prog = self._make_program([])
        code = PythonBackend().generate(prog)
        assert "pass" in code

    def test_c_struct_codegen(self):
        prog = Program(structs=[Struct("Point", [("x", IntType), ("y", FloatType)])])
        code = CBackend().generate(prog)
        assert "struct Point" in code
        assert "int x;" in code
        assert "double y;" in code

    def test_python_struct_codegen(self):
        prog = Program(structs=[Struct("Point", [("x", IntType), ("y", FloatType)])])
        code = PythonBackend().generate(prog)
        assert "class Point:" in code
        assert "x: int" in code
        assert "y: float" in code

    def test_c_field_access_codegen(self):
        prog = self._make_program([Return(FieldAccess(Var("p"), "x"))])
        code = CBackend().generate(prog)
        assert "return p.x;" in code

    def test_c_call_codegen(self):
        prog = self._make_program([ExprStmt(Call(Var("add"), [IntLiteral(1), IntLiteral(2)]))])
        code = CBackend().generate(prog)
        assert "add(1, 2);" in code

    def test_c_void_return(self):
        prog = self._make_program([Return()])
        code = CBackend().generate(prog)
        assert "return;" in code

    def test_c_type_mapping(self):
        """Verify all primitive types map to correct C types."""
        backend = CBackend()
        assert backend._type_to_str(IntType) == "int"
        assert backend._type_to_str(FloatType) == "double"
        assert backend._type_to_str(BoolType) == "bool"
        assert backend._type_to_str(StringType) == "char*"
        assert backend._type_to_str(VoidType) == "void"
        assert backend._type_to_str(AnyType) == "void*"


# ---------------------------------------------------------------------------
# CLI edge cases
# ---------------------------------------------------------------------------


class TestCLIEdgeCases:
    def test_cross_language_transpile(self, tmp_path, capsys):
        """Transpile Python -> C."""
        import sys
        from unittest.mock import patch
        from transpiler.cli.main import main

        test_file = tmp_path / "test.py"
        test_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

        with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "c"]):
            main()

        out, err = capsys.readouterr()
        assert err == ""
        assert "int add(int a, int b)" in out
        assert "return (a + b);" in out

    def test_python_to_js_transpile(self, tmp_path, capsys):
        import sys
        from unittest.mock import patch
        from transpiler.cli.main import main

        test_file = tmp_path / "test.py"
        test_file.write_text('def greet():\n    return "hello"\n')

        with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "js"]):
            main()

        out, err = capsys.readouterr()
        assert err == ""
        assert "function greet()" in out
        assert '"hello"' in out

    def test_crlf_input_handled(self, tmp_path, capsys):
        """CRLF line endings should not break parsing."""
        import sys
        from unittest.mock import patch
        from transpiler.cli.main import main

        test_file = tmp_path / "test.py"
        test_file.write_bytes(b"def add(a: int, b: int) -> int:\r\n    return a + b\r\n")

        with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "python"]):
            main()

        out, err = capsys.readouterr()
        assert err == ""
        assert "def add" in out

    def test_missing_to_flag(self, capsys):
        """Omitting --to should cause argparse error."""
        import sys
        from unittest.mock import patch
        from transpiler.cli.main import main

        with patch.object(sys, "argv", ["transpiler", "some_file.py"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 2  # argparse error code
