from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.backend.common import escape_c_style, safe_ident, JAVA_KEYWORDS


class JavaBackend:
    def __init__(self):
        self.indent_level = 0
        self.structs = {}

    def generate(self, program: Program) -> str:
        self.structs = {s.name: s for s in program.structs}
        lines = ["public class Main {", ""]
        self.indent_level += 1

        for struct in program.structs:
            lines.append(self._generate_class(struct))
        for glob in program.globals:
            lines.append(self._generate_global(glob))
        for function in program.functions:
            lines.append(self._generate_function(function))

        self.indent_level -= 1
        lines.append("}\n")
        return "\n".join(lines)

    def _name(self, name: str) -> str:
        return safe_ident(name, JAVA_KEYWORDS)

    def _generate_global(self, node: GlobalVar) -> str:
        value = self._generate_expr(node.value) if node.value is not None else "null"
        return self._indent(
            f"public static {self._type_to_str(node.type)} {self._name(node.name)} = {value};\n"
        )

    def _generate_class(self, node: Struct) -> str:
        lines = [self._indent(f"public static class {self._name(node.name)} {{")]
        self.indent_level += 1
        for name, typ in node.fields:
            lines.append(self._indent(f"public {self._type_to_str(typ)} {self._name(name)};"))
        params = ", ".join(
            f"{self._type_to_str(typ)} {self._name(name)}" for name, typ in node.fields
        )
        lines.append(self._indent(f"public {self._name(node.name)}({params}) {{"))
        self.indent_level += 1
        for name, _ in node.fields:
            lines.append(self._indent(f"this.{self._name(name)} = {self._name(name)};"))
        self.indent_level -= 1
        lines.append(self._indent("}"))
        self.indent_level -= 1
        lines.append(self._indent("}\n"))
        return "\n".join(lines)

    def _generate_function(self, node: Function) -> str:
        params = []
        for p in node.params:
            params.append(f"{self._type_to_str(p.type)} {self._name(p.name)}")

        ret_type = self._type_to_str(node.return_type)

        if node.name == "main" and not node.params:
            lines = [self._indent("public static void main(String[] args) {")]
        else:
            lines = [
                self._indent(
                    f"public static {ret_type} {self._name(node.name)}({', '.join(params)}) {{"
                )
            ]

        self.indent_level += 1
        body_str = self._generate_block(node.body)
        if body_str:
            lines.append(body_str)
        self.indent_level -= 1
        lines.append(self._indent("}\n"))
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
            return f"{self._type_to_str(node.type)} {self._name(node.name)} = {self._generate_expr(node.value)};"
        elif isinstance(node, Assign):
            return f"{self._generate_expr(node.target)} = {self._generate_expr(node.value)};"
        elif isinstance(node, ExprStmt):
            return f"{self._generate_expr(node.expr)};"
        elif isinstance(node, Block):
            return self._generate_block(node)
        elif isinstance(node, If):
            res = f"if ({self._generate_expr(node.condition)}) {{\n"
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
            res = f"while ({self._generate_expr(node.condition)}) {{\n"
            self.indent_level += 1
            res += self._generate_block(node.body)
            self.indent_level -= 1
            res += f"\n{self._indent('}')}"
            return res.strip()
        elif isinstance(node, For):
            init_str = self._generate_stmt(node.init).rstrip(";")
            update_str = self._generate_stmt(node.update).rstrip(";")
            res = f"for ({init_str}; {self._generate_expr(node.condition)}; {update_str}) {{\n"
            self.indent_level += 1
            res += self._generate_block(node.body)
            self.indent_level -= 1
            res += f"\n{self._indent('}')}"
            return res.strip()
        elif isinstance(node, Break):
            return "break;"
        elif isinstance(node, Continue):
            return "continue;"
        raise NotImplementedError(f"JavaBackend: unsupported statement {type(node).__name__}")

    def _generate_expr(self, node: Expr) -> str:
        if isinstance(node, IntLiteral):
            return str(node.value)
        elif isinstance(node, FloatLiteral):
            return str(node.value)
        elif isinstance(node, BoolLiteral):
            return "true" if node.value else "false"
        elif isinstance(node, StringLiteral):
            return f'"{escape_c_style(node.value)}"'
        elif isinstance(node, NullLiteral):
            return "null"
        elif isinstance(node, Var):
            return self._name(node.name)
        elif isinstance(node, Binary):
            return f"({self._generate_expr(node.left)} {node.op.value} {self._generate_expr(node.right)})"
        elif isinstance(node, Unary):
            op = "!" if node.op == UnOp.NOT else "-"
            return f"({op}{self._generate_expr(node.expr)})"
        elif isinstance(node, Cast):
            return f"(({self._type_to_str(node.target_type)}){self._generate_expr(node.expr)})"
        elif isinstance(node, IndexAccess):
            return f"{self._generate_expr(node.collection)}[{self._generate_expr(node.index)}]"
        elif isinstance(node, ArrayInit):
            elements = ", ".join(self._generate_expr(e) for e in node.elements)
            return f"new Object[]{{{elements}}}"
        elif isinstance(node, MapInit):
            entries = ", ".join(
                f"{self._generate_expr(k)}, {self._generate_expr(v)}" for k, v in node.entries
            )
            return f"Map.of({entries})"
        elif isinstance(node, StructInit):
            struct = self.structs.get(node.name)
            field_order = [f[0] for f in struct.fields] if struct else list(node.fields.keys())
            args = ", ".join(
                self._generate_expr(node.fields[f]) for f in field_order if f in node.fields
            )
            return f"new {self._name(node.name)}({args})"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            if func == "print":
                func = "System.out.println"
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{self._name(node.field)}"
        raise NotImplementedError(f"JavaBackend: unsupported expression {type(node).__name__}")

    def _type_to_str(self, t: Type) -> str:
        if t.kind == TypeKind.INT:
            return "int"
        elif t.kind == TypeKind.FLOAT:
            return "double"
        elif t.kind == TypeKind.BOOL:
            return "boolean"
        elif t.kind == TypeKind.STRING:
            return "String"
        elif t.kind == TypeKind.VOID:
            return "void"
        elif t.kind == TypeKind.STRUCT:
            return t.name
        return "Object"

    def _indent(self, line: str) -> str:
        return "    " * self.indent_level + line
