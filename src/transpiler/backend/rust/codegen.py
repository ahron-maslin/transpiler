from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.backend.common import escape_c_style, safe_ident, RUST_KEYWORDS


class RustBackend:
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
        return safe_ident(name, RUST_KEYWORDS)

    def _generate_global(self, node: GlobalVar) -> str:
        value = self._generate_expr(node.value) if node.value is not None else "0"
        return f"static mut {self._name(node.name)}: {self._type_to_str(node.type)} = {value};\n"

    def _generate_struct(self, node: Struct) -> str:
        lines = [f"struct {node.name} {{"]
        self.indent_level += 1
        for name, typ in node.fields:
            lines.append(self._indent(f"{self._name(name)}: {self._type_to_str(typ)},"))
        self.indent_level -= 1
        lines.append("}\n")
        return "\n".join(lines)

    def _generate_function(self, node: Function) -> str:
        params = []
        for p in node.params:
            params.append(f"{self._name(p.name)}: {self._type_to_str(p.type)}")

        ret_type = self._type_to_str(node.return_type)
        ret_str = f" -> {ret_type}" if ret_type and ret_type != "()" else ""

        lines = [f"fn {self._name(node.name)}({', '.join(params)}){ret_str} {{"]
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
            return f"let mut {self._name(node.name)}: {self._type_to_str(node.type)} = {self._generate_expr(node.value)};"
        elif isinstance(node, Assign):
            return f"{self._generate_expr(node.target)} = {self._generate_expr(node.value)};"
        elif isinstance(node, ExprStmt):
            return f"{self._generate_expr(node.expr)};"
        elif isinstance(node, Block):
            return self._generate_block(node)
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
        elif isinstance(node, For):
            init_str = self._generate_stmt(node.init)
            res = f"{init_str}\n{self._indent(f'while {self._generate_expr(node.condition)} {{')}\n"
            self.indent_level += 1
            body_str = self._generate_block(node.body)
            update_str = self._indent(self._generate_stmt(node.update))
            res += (body_str + "\n" if body_str.strip() else "") + update_str
            self.indent_level -= 1
            res += f"\n{self._indent('}')}"
            return res.strip()
        elif isinstance(node, Break):
            return "break;"
        elif isinstance(node, Continue):
            return "continue;"
        raise NotImplementedError(f"RustBackend: unsupported statement {type(node).__name__}")

    def _generate_expr(self, node: Expr) -> str:
        if isinstance(node, IntLiteral):
            return str(node.value)
        elif isinstance(node, FloatLiteral):
            return str(node.value)
        elif isinstance(node, BoolLiteral):
            return "true" if node.value else "false"
        elif isinstance(node, StringLiteral):
            return f'"{escape_c_style(node.value)}".to_string()'
        elif isinstance(node, NullLiteral):
            return "None"
        elif isinstance(node, Var):
            return self._name(node.name)
        elif isinstance(node, Binary):
            return f"({self._generate_expr(node.left)} {node.op.value} {self._generate_expr(node.right)})"
        elif isinstance(node, Unary):
            op = "!" if node.op == UnOp.NOT else "-"
            return f"({op}{self._generate_expr(node.expr)})"
        elif isinstance(node, Cast):
            expr = self._generate_expr(node.expr)
            if node.target_type.kind == TypeKind.STRING:
                return f"({expr}).to_string()"
            return f"({expr} as {self._type_to_str(node.target_type)})"
        elif isinstance(node, IndexAccess):
            return f"{self._generate_expr(node.collection)}[{self._generate_expr(node.index)}]"
        elif isinstance(node, ArrayInit):
            return f"vec![{', '.join(self._generate_expr(e) for e in node.elements)}]"
        elif isinstance(node, MapInit):
            entries = ", ".join(
                f"({self._generate_expr(k)}, {self._generate_expr(v)})" for k, v in node.entries
            )
            return f"std::collections::HashMap::from([{entries}])"
        elif isinstance(node, StructInit):
            fields = ", ".join(
                f"{self._name(k)}: {self._generate_expr(v)}" for k, v in node.fields.items()
            )
            return f"{node.name} {{ {fields} }}"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            if func == "print":
                func = "println!"
                args = [self._generate_expr(arg) for arg in node.args]
                return f'{func}("{{}}", {", ".join(args)})'
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{self._name(node.field)}"
        raise NotImplementedError(f"RustBackend: unsupported expression {type(node).__name__}")

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
