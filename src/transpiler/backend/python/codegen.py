from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.backend.common import escape_python_str, safe_ident, PYTHON_KEYWORDS


class PythonBackend:
    def __init__(self):
        self.indent_level = 0

    def generate(self, program: Program) -> str:
        lines = []
        for struct in program.structs:
            lines.append(self._generate_struct(struct))
        for glob in program.globals:
            lines.append(self._generate_global(glob))
        for function in program.functions:
            lines.append(self._generate_function(function))
        return "\n".join(lines)

    def _name(self, name: str) -> str:
        return safe_ident(name, PYTHON_KEYWORDS)

    def _generate_global(self, node: GlobalVar) -> str:
        value = self._generate_expr(node.value) if node.value is not None else "None"
        return f"{self._name(node.name)}: {self._type_to_str(node.type)} = {value}"

    def _generate_struct(self, node: Struct) -> str:
        lines = [f"class {self._name(node.name)}:"]
        self.indent_level += 1
        if not node.fields:
            lines.append(self._indent("pass"))
        else:
            for name, typ in node.fields:
                lines.append(self._indent(f"{self._name(name)}: {self._type_to_str(typ)}"))
            params = ", ".join(
                f"{self._name(name)}: {self._type_to_str(typ)}" for name, typ in node.fields
            )
            lines.append(self._indent(f"def __init__(self, {params}):"))
            self.indent_level += 1
            for name, _ in node.fields:
                lines.append(self._indent(f"self.{self._name(name)} = {self._name(name)}"))
            self.indent_level -= 1
        self.indent_level -= 1
        return "\n".join(lines) + "\n"

    def _generate_function(self, node: Function) -> str:
        params = []
        for p in node.params:
            ptype = self._type_to_str(p.type)
            pname = self._name(p.name)
            params.append(f"{pname}: {ptype}" if ptype else pname)

        ret_type = self._type_to_str(node.return_type)
        ret_str = f" -> {ret_type}" if ret_type and ret_type != "Any" else ""

        lines = [f"def {self._name(node.name)}({', '.join(params)}){ret_str}:"]
        self.indent_level += 1
        body_str = self._generate_block(node.body)
        if not body_str.strip():
            lines.append(self._indent("pass"))
        else:
            lines.append(body_str)
        self.indent_level -= 1
        return "\n".join(lines) + "\n"

    def _generate_block(self, node: Block) -> str:
        lines = []
        for stmt in node.statements:
            stmt_str = self._generate_stmt(stmt)
            if stmt_str:
                lines.append(self._indent(stmt_str))
        return "\n".join(lines)

    def _generate_stmt(self, node: Stmt) -> str:
        if isinstance(node, Return):
            if node.value:
                return f"return {self._generate_expr(node.value)}"
            return "return"
        elif isinstance(node, Let):
            return f"{self._name(node.name)}: {self._type_to_str(node.type)} = {self._generate_expr(node.value)}"
        elif isinstance(node, Assign):
            return f"{self._generate_expr(node.target)} = {self._generate_expr(node.value)}"
        elif isinstance(node, ExprStmt):
            return self._generate_expr(node.expr)
        elif isinstance(node, If):
            res = f"if {self._generate_expr(node.condition)}:\n"
            self.indent_level += 1
            res += self._generate_block(node.then_block)
            self.indent_level -= 1
            if node.else_block:
                res += f"\n{self._indent('else:')}\n"
                self.indent_level += 1
                res += self._generate_block(node.else_block)
                self.indent_level -= 1
            return res.strip()
        elif isinstance(node, While):
            res = f"while {self._generate_expr(node.condition)}:\n"
            self.indent_level += 1
            res += self._generate_block(node.body)
            self.indent_level -= 1
            return res.strip()
        elif isinstance(node, For):
            init_str = self._generate_stmt(node.init)
            res = f"{init_str}\n{self._indent(f'while {self._generate_expr(node.condition)}:')}\n"
            self.indent_level += 1
            body_str = self._generate_block(node.body)
            update_str = self._indent(self._generate_stmt(node.update))
            res += (body_str + "\n" if body_str.strip() else "") + update_str
            self.indent_level -= 1
            return res.strip()
        elif isinstance(node, Break):
            return "break"
        elif isinstance(node, Continue):
            return "continue"
        raise NotImplementedError(f"PythonBackend: unsupported statement {type(node).__name__}")

    def _generate_expr(self, node: Expr) -> str:
        if isinstance(node, IntLiteral):
            return str(node.value)
        elif isinstance(node, FloatLiteral):
            return str(node.value)
        elif isinstance(node, BoolLiteral):
            return "True" if node.value else "False"
        elif isinstance(node, StringLiteral):
            return f'"{escape_python_str(node.value)}"'
        elif isinstance(node, NullLiteral):
            return "None"
        elif isinstance(node, Var):
            return self._name(node.name)
        elif isinstance(node, Binary):
            op = {BinOp.AND: "and", BinOp.OR: "or"}.get(node.op, node.op.value)
            return f"({self._generate_expr(node.left)} {op} {self._generate_expr(node.right)})"
        elif isinstance(node, Unary):
            if node.op == UnOp.NOT:
                return f"(not {self._generate_expr(node.expr)})"
            return f"(-{self._generate_expr(node.expr)})"
        elif isinstance(node, Cast):
            conv = {
                TypeKind.INT: "int",
                TypeKind.FLOAT: "float",
                TypeKind.STRING: "str",
                TypeKind.BOOL: "bool",
            }.get(node.target_type.kind)
            expr = self._generate_expr(node.expr)
            return f"{conv}({expr})" if conv else expr
        elif isinstance(node, IndexAccess):
            return f"{self._generate_expr(node.collection)}[{self._generate_expr(node.index)}]"
        elif isinstance(node, ArrayInit):
            return f"[{', '.join(self._generate_expr(e) for e in node.elements)}]"
        elif isinstance(node, MapInit):
            entries = ", ".join(
                f"{self._generate_expr(k)}: {self._generate_expr(v)}" for k, v in node.entries
            )
            return f"{{{entries}}}"
        elif isinstance(node, StructInit):
            args = ", ".join(
                f"{self._name(k)}={self._generate_expr(v)}" for k, v in node.fields.items()
            )
            return f"{self._name(node.name)}({args})"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{self._name(node.field)}"
        raise NotImplementedError(f"PythonBackend: unsupported expression {type(node).__name__}")

    def _type_to_str(self, t: Type) -> str:
        if t.kind == TypeKind.INT:
            return "int"
        elif t.kind == TypeKind.FLOAT:
            return "float"
        elif t.kind == TypeKind.BOOL:
            return "bool"
        elif t.kind == TypeKind.STRING:
            return "str"
        return "Any"

    def _indent(self, line: str) -> str:
        return "    " * self.indent_level + line
