from transpiler.ir.nodes import *
from transpiler.ir.types import *


class RustBackend:
    def __init__(self):
        self.indent_level = 0

    def generate(self, program: Program) -> str:
        lines = []
        for struct in program.structs:
            lines.append(self._generate_struct(struct))
        for function in program.functions:
            lines.append(self._generate_function(function))
        return "\n".join(lines)

    def _generate_struct(self, node: Struct) -> str:
        lines = [f"struct {node.name} {{"]
        self.indent_level += 1
        for name, typ in node.fields:
            lines.append(self._indent(f"{name}: {self._type_to_str(typ)},"))
        self.indent_level -= 1
        lines.append("}\n")
        return "\n".join(lines)

    def _generate_function(self, node: Function) -> str:
        params = []
        for p in node.params:
            params.append(f"{p.name}: {self._type_to_str(p.type)}")

        ret_type = self._type_to_str(node.return_type)
        ret_str = f" -> {ret_type}" if ret_type and ret_type != "()" else ""

        lines = [f"fn {node.name}({', '.join(params)}){ret_str} {{"]
        self.indent_level += 1
        body_str = self._generate_block(node.body)
        if body_str:
            lines.append(body_str)
        self.indent_level -= 1
        lines.append("}\n")
        return "\n".join(lines)

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
                return f"return {self._generate_expr(node.value)};"
            return "return;"
        elif isinstance(node, Let):
            return f"let mut {node.name}: {self._type_to_str(node.type)} = {self._generate_expr(node.value)};"
        elif isinstance(node, Assign):
            return f"{self._generate_expr(node.target)} = {self._generate_expr(node.value)};"
        elif isinstance(node, ExprStmt):
            return f"{self._generate_expr(node.expr)};"
        elif isinstance(node, If):
            res = f"if {self._generate_expr(node.condition)} {{\n"
            self.indent_level += 1
            res += self._generate_block(node.then_block)
            self.indent_level -= 1
            res += f"\n{self._indent('}')}"
            if node.else_block:
                res += " else {\n"
                self.indent_level += 1
                res += self._generate_block(node.else_block)
                self.indent_level -= 1
                res += f"\n{self._indent('}')}"
            return res.strip()
        elif isinstance(node, While):
            res = f"while {self._generate_expr(node.condition)} {{\n"
            self.indent_level += 1
            res += self._generate_block(node.body)
            self.indent_level -= 1
            res += f"\n{self._indent('}')}"
            return res.strip()
        return ""

    def _generate_expr(self, node: Expr) -> str:
        if isinstance(node, IntLiteral):
            return str(node.value)
        elif isinstance(node, FloatLiteral):
            return str(node.value)
        elif isinstance(node, BoolLiteral):
            return "true" if node.value else "false"
        elif isinstance(node, StringLiteral):
            return f'"{node.value}".to_string()'
        elif isinstance(node, NullLiteral):
            return "None"
        elif isinstance(node, Var):
            return node.name
        elif isinstance(node, Binary):
            return f"({self._generate_expr(node.left)} {node.op.value} {self._generate_expr(node.right)})"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            if func == "print":
                func = "println!"
                args = [self._generate_expr(arg) for arg in node.args]
                return f'{func}("{{}}", {", ".join(args)})'
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{node.field}"
        return ""

    def _type_to_str(self, t: Type) -> str:
        if t.kind == TypeKind.INT:
            return "i32"
        elif t.kind == TypeKind.FLOAT:
            return "f64"
        elif t.kind == TypeKind.BOOL:
            return "bool"
        elif t.kind == TypeKind.STRING:
            return "String"
        elif t.kind == TypeKind.VOID:
            return "()"
        elif t.kind == TypeKind.STRUCT:
            return t.name
        return "Box<dyn std::any::Any>"

    def _indent(self, line: str) -> str:
        return "    " * self.indent_level + line
