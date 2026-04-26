from ir.nodes import *
from ir.types import *

class JSBackend:
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
        lines = [f"class {node.name} {{"]
        self.indent_level += 1
        
        if node.fields:
            params = [name for name, _ in node.fields]
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
        params = [p.name for p in node.params]
        lines = [f"function {node.name}({', '.join(params)}) {{"]
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
            return f"let {node.name} = {self._generate_expr(node.value)};"
        elif isinstance(node, Assign):
            return f"{self._generate_expr(node.target)} = {self._generate_expr(node.value)};"
        elif isinstance(node, ExprStmt):
            return f"{self._generate_expr(node.expr)};"
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
        return ""
        
    def _generate_expr(self, node: Expr) -> str:
        if isinstance(node, IntLiteral): return str(node.value)
        elif isinstance(node, FloatLiteral): return str(node.value)
        elif isinstance(node, BoolLiteral): return "true" if node.value else "false"
        elif isinstance(node, StringLiteral): return f'"{node.value}"'
        elif isinstance(node, NullLiteral): return "null"
        elif isinstance(node, Var): return node.name
        elif isinstance(node, Binary):
            op = node.op.value
            if node.op == BinOp.EQ: op = "==="
            if node.op == BinOp.NEQ: op = "!=="
            return f"({self._generate_expr(node.left)} {op} {self._generate_expr(node.right)})"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            if func == "print":
                func = "console.log"
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{node.field}"
        return ""
        
    def _indent(self, line: str) -> str:
        return "    " * self.indent_level + line
