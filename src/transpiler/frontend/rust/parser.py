import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

RUST_LANGUAGE = Language(tsrust.language(), "rust")


class RustFrontend:
    def __init__(self):
        self.parser = Parser()
        self.parser.set_language(RUST_LANGUAGE)

    def parse(self, source_code: str) -> Program:
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return self._visit_program(tree.root_node)

    def _visit_program(self, node: Node) -> Program:
        program = Program()
        for child in node.children:
            if child.type == "function_item":
                program.functions.append(self._visit_function(child))
        return program

    def _visit_function(self, node: Node) -> Function:
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        body_node = node.child_by_field_name("body")
        ret_node = node.child_by_field_name("return_type")

        name = name_node.text.decode("utf8") if name_node else ""

        params = []
        if params_node:
            for child in params_node.children:
                if child.type == "parameter":
                    pname_node = child.child_by_field_name("pattern")
                    ptype_node = child.child_by_field_name("type")
                    if pname_node:
                        pname = pname_node.text.decode("utf8")
                        ptype = (
                            self._parse_type(ptype_node.text.decode("utf8"))
                            if ptype_node
                            else AnyType
                        )
                        params.append(Param(name=pname, type=ptype))

        ret_type = self._parse_type(ret_node.text.decode("utf8")) if ret_node else VoidType
        body = self._visit_block(body_node) if body_node else Block()

        return Function(name=name, params=params, return_type=ret_type, body=body)

    def _parse_type(self, type_str: str) -> Type:
        if type_str == "i32" or type_str == "i64":
            return IntType
        if type_str == "f32" or type_str == "f64":
            return FloatType
        if type_str == "bool":
            return BoolType
        if type_str == "String" or type_str == "&str":
            return StringType
        if type_str == "()":
            return VoidType
        return AnyType

    def _visit_block(self, node: Node) -> Block:
        stmts = []
        for child in node.children:
            if child.is_named:
                stmt = self._visit_stmt(child)
                if stmt:
                    stmts.append(stmt)
        return Block(statements=stmts)

    def _visit_stmt(self, node: Node) -> Optional[Stmt]:
        if node.type == "let_declaration":
            pat_node = node.child_by_field_name("pattern")
            val_node = node.child_by_field_name("value")
            type_node = node.child_by_field_name("type")
            name = pat_node.text.decode("utf8") if pat_node else ""
            val = self._visit_expr(val_node) if val_node else NullLiteral()
            typ = self._parse_type(type_node.text.decode("utf8")) if type_node else AnyType
            return Let(name=name, type=typ, value=val)
        elif node.type == "expression_statement":
            expr_node = None
            for child in node.children:
                if child.is_named:
                    expr_node = child
                    break
            if expr_node:
                if expr_node.type == "assignment_expression":
                    left = expr_node.child_by_field_name("left")
                    right = expr_node.child_by_field_name("right")
                    if left and right:
                        return Assign(target=self._visit_expr(left), value=self._visit_expr(right))
                elif expr_node.type == "return_expression":
                    val = None
                    for child in expr_node.children:
                        if child.is_named:
                            val = self._visit_expr(child)
                            break
                    return Return(value=val)
                return ExprStmt(expr=self._visit_expr(expr_node))
        elif node.type == "return_expression":
            val = None
            for child in node.children:
                if child.is_named:
                    val = self._visit_expr(child)
                    break
            return Return(value=val)
        elif node.is_named:
            # check if it's the last expression in block (implicit return)
            # but we just wrap in ExprStmt for MVP
            return ExprStmt(expr=self._visit_expr(node))

        return None

    def _visit_expr(self, node: Node) -> Expr:
        if node.type == "integer_literal":
            return IntLiteral(int(node.text.decode("utf8").replace("_", "")))
        elif node.type == "float_literal":
            return FloatLiteral(float(node.text.decode("utf8").replace("_", "")))
        elif node.type == "string_literal":
            return StringLiteral(node.text.decode("utf8").strip('"'))
        elif node.type == "boolean_literal":
            return BoolLiteral(node.text.decode("utf8") == "true")
        elif node.type == "identifier":
            return Var(node.text.decode("utf8"))
        elif node.type == "binary_expression":
            left_node = node.child_by_field_name("left")
            right_node = node.child_by_field_name("right")
            op_node = node.child_by_field_name("operator")

            if left_node and right_node and op_node:
                op_str = op_node.text.decode("utf8")
                op = None
                if op_str == "+":
                    op = BinOp.ADD
                elif op_str == "-":
                    op = BinOp.SUB
                elif op_str == "*":
                    op = BinOp.MUL
                elif op_str == "/":
                    op = BinOp.DIV
                elif op_str == "%":
                    op = BinOp.MOD
                elif op_str == "==":
                    op = BinOp.EQ
                elif op_str == "!=":
                    op = BinOp.NEQ
                elif op_str == "<":
                    op = BinOp.LT
                elif op_str == "<=":
                    op = BinOp.LTE
                elif op_str == ">":
                    op = BinOp.GT
                elif op_str == ">=":
                    op = BinOp.GTE
                elif op_str == "&&":
                    op = BinOp.AND
                elif op_str == "||":
                    op = BinOp.OR

                if op:
                    return Binary(
                        op=op, left=self._visit_expr(left_node), right=self._visit_expr(right_node)
                    )
        return NullLiteral()
