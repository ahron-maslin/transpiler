from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.backend.common import escape_c_style, safe_ident, JS_KEYWORDS


class JSBackend:
    def __init__(self):
        self.indent_level = 0
        self.structs = {}

    def generate(self, program: Program) -> str:
        self.structs = {s.name: s for s in program.structs}
        lines = []
        for struct in program.structs:
            lines.append(self._generate_struct(struct))
        for glob in program.globals:
            lines.append(self._generate_global(glob))
        for function in program.functions:
            lines.append(self._generate_function(function))
        return "\n".join(lines)

    def _name(self, name: str) -> str:
        return safe_ident(name, JS_KEYWORDS)

    def _generate_global(self, node: GlobalVar) -> str:
        value = self._generate_expr(node.value) if node.value is not None else "null"
        return f"let {self._name(node.name)} = {value};\n"

    def _generate_struct(self, node: Struct) -> str:
        lines = [f"class {node.name} {{"]
        self.indent_level += 1

        if node.fields:
            params = [self._name(name) for name, _ in node.fields]
            lines.append(self._indent(f"constructor({', '.join(params)}) {{"))
            self.indent_level += 1
            for name in params:
                lines.append(self._indent(f"this.{name} = {name};"))
            self.indent_level -= 1
            lines.append(self._indent("}"))

        self.indent_level -= 1
        lines.append("}\n")
        return "\n".join(lines)

    def _generate_function(self, node: Function) -> str:
        params = [self._name(p.name) for p in node.params]
        lines = [f"function {self._name(node.name)}({', '.join(params)}) {{"]
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
            return f"let {self._name(node.name)} = {self._generate_expr(node.value)};"
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
        raise NotImplementedError(f"JSBackend: unsupported statement {type(node).__name__}")

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
            op = node.op.value
            if node.op == BinOp.EQ:
                op = "==="
            if node.op == BinOp.NEQ:
                op = "!=="
            return f"({self._generate_expr(node.left)} {op} {self._generate_expr(node.right)})"
        elif isinstance(node, Unary):
            op = "!" if node.op == UnOp.NOT else "-"
            return f"({op}{self._generate_expr(node.expr)})"
        elif isinstance(node, Cast):
            conv = {
                TypeKind.INT: "Number",
                TypeKind.FLOAT: "Number",
                TypeKind.STRING: "String",
                TypeKind.BOOL: "Boolean",
            }.get(node.target_type.kind)
            expr = self._generate_expr(node.expr)
            return f"{conv}({expr})" if conv else expr
        elif isinstance(node, IndexAccess):
            return f"{self._generate_expr(node.collection)}[{self._generate_expr(node.index)}]"
        elif isinstance(node, ArrayInit):
            return f"[{', '.join(self._generate_expr(e) for e in node.elements)}]"
        elif isinstance(node, MapInit):
            entries = ", ".join(
                f"[{self._generate_expr(k)}, {self._generate_expr(v)}]" for k, v in node.entries
            )
            return f"new Map([{entries}])"
        elif isinstance(node, StructInit):
            struct = self.structs.get(node.name)
            field_order = [f[0] for f in struct.fields] if struct else list(node.fields.keys())
            args = ", ".join(
                self._generate_expr(node.fields[f]) for f in field_order if f in node.fields
            )
            return f"new {node.name}({args})"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            if func == "print":
                func = "console.log"
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{self._name(node.field)}"
        raise NotImplementedError(f"JSBackend: unsupported expression {type(node).__name__}")

    def _indent(self, line: str) -> str:
        return "    " * self.indent_level + line
