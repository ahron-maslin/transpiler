from typing import Dict
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from transpiler.backend.common import escape_c_style, safe_ident, C_KEYWORDS


class CBackend:
    def __init__(self):
        self.indent_level = 0
        self.var_types: Dict[str, Type] = {}
        self.structs = {}

    def generate(self, program: Program) -> str:
        self.structs = {s.name: s for s in program.structs}
        lines = ['#include "runtime/c/transpiler_runtime.h"', ""]

        for struct in program.structs:
            lines.append(f"typedef struct {struct.name} {struct.name};")
        if program.structs:
            lines.append("")

        for struct in program.structs:
            lines.append(self._generate_struct(struct))

        for glob in program.globals:
            lines.append(self._generate_global(glob))

        for function in program.functions:
            lines.append(self._generate_function(function))

        return "\n".join(lines)

    def _name(self, name: str) -> str:
        return safe_ident(name, C_KEYWORDS)

    def _generate_global(self, node: GlobalVar) -> str:
        value = self._generate_expr(node.value) if node.value is not None else "0"
        return f"{self._type_to_str(node.type)} {self._name(node.name)} = {value};\n"

    def _generate_struct(self, node: Struct) -> str:
        lines = [f"struct {node.name} {{"]
        self.indent_level += 1
        for name, typ in node.fields:
            lines.append(self._indent(f"{self._type_to_str(typ)} {self._name(name)};"))
        self.indent_level -= 1
        lines.append("};\n")
        return "\n".join(lines)

    def _generate_function(self, node: Function) -> str:
        self.var_types = {}
        params = []
        for p in node.params:
            self.var_types[p.name] = p.type
            params.append(f"{self._type_to_str(p.type)} {self._name(p.name)}")

        ret_type = self._type_to_str(node.return_type)

        lines = [f"{ret_type} {self._name(node.name)}({', '.join(params)}) {{"]
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
            self.var_types[node.name] = node.type
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
        raise NotImplementedError(f"CBackend: unsupported statement {type(node).__name__}")

    def _infer_arg_type(self, node: Expr) -> Type:
        if isinstance(node, StringLiteral):
            return StringType
        elif isinstance(node, FloatLiteral):
            return FloatType
        elif isinstance(node, BoolLiteral):
            return BoolType
        elif isinstance(node, IntLiteral):
            return IntType
        elif isinstance(node, Var):
            return self.var_types.get(node.name, AnyType)
        return AnyType

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
            return "NULL"
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
            elements = [self._generate_expr(e) for e in node.elements]
            elem_type = (
                self._type_to_str(self._infer_arg_type(node.elements[0]))
                if node.elements
                else "int"
            )
            return f"({elem_type}[]){{{', '.join(elements)}}}"
        elif isinstance(node, MapInit):
            raise NotImplementedError(
                "CBackend: map literals are not supported (no runtime hashmap)"
            )
        elif isinstance(node, StructInit):
            fields = ", ".join(
                f".{self._name(k)} = {self._generate_expr(v)}" for k, v in node.fields.items()
            )
            return f"(struct {node.name}){{{fields}}}"
        elif isinstance(node, Call):
            func = self._generate_expr(node.function)
            if func == "print":
                arg_type = self._infer_arg_type(node.args[0]) if len(node.args) == 1 else AnyType
                func = {
                    TypeKind.STRING: "print_str",
                    TypeKind.FLOAT: "print_float",
                    TypeKind.BOOL: "print_bool",
                }.get(arg_type.kind, "print_int")
            args = [self._generate_expr(arg) for arg in node.args]
            return f"{func}({', '.join(args)})"
        elif isinstance(node, FieldAccess):
            return f"{self._generate_expr(node.object)}.{self._name(node.field)}"
        raise NotImplementedError(f"CBackend: unsupported expression {type(node).__name__}")

    def _type_to_str(self, t: Type) -> str:
        if t.kind == TypeKind.INT:
            return "int"
        elif t.kind == TypeKind.FLOAT:
            return "double"
        elif t.kind == TypeKind.BOOL:
            return "bool"
        elif t.kind == TypeKind.STRING:
            return "char*"
        elif t.kind == TypeKind.VOID:
            return "void"
        elif t.kind == TypeKind.STRUCT:
            return f"struct {t.name}"
        return "void*"

    def _indent(self, line: str) -> str:
        return "    " * self.indent_level + line
