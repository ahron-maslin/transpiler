import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

JS_LANGUAGE = Language(tsjavascript.language(), "javascript")


class JSFrontend:
    def __init__(self):
        self.parser = Parser(JS_LANGUAGE)

    def parse(self, source_code: str) -> Program:
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return self._visit_program(tree.root_node)

    def _visit_program(self, node: Node) -> Program:
        program = Program()
        for child in node.children:
            if child.type == "function_declaration":
                program.functions.append(self._visit_function(child))
            elif child.type == "class_declaration":
                pass  # TODO: structs
        return program

    def _visit_function(self, node: Node) -> Function:
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        body_node = node.child_by_field_name("body")

        name = name_node.text.decode("utf8") if name_node else ""

        params = []
        if params_node:
            for child in params_node.children:
                if child.type == "identifier":
                    params.append(Param(name=child.text.decode("utf8"), type=AnyType))

        body = self._visit_block(body_node) if body_node else Block()

        return Function(name=name, params=params, return_type=AnyType, body=body)

    def _visit_block(self, node: Node) -> Block:
        stmts = []
        for child in node.children:
            if child.is_named:
                stmt = self._visit_stmt(child)
                if stmt:
                    stmts.append(stmt)
        return Block(statements=stmts)

    def _visit_stmt(self, node: Node) -> Optional[Stmt]:
        if node.type == "return_statement":
            value = None
            for child in node.children:
                if child.is_named:
                    value = self._visit_expr(child)
                    break
            return Return(value=value)
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
                return ExprStmt(expr=self._visit_expr(expr_node))
        elif node.type == "lexical_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    name = name_node.text.decode("utf8") if name_node else ""
                    val = self._visit_expr(val_node) if val_node else NullLiteral()
                    return Let(name=name, type=AnyType, value=val)
        return None

    def _visit_expr(self, node: Node) -> Expr:
        if node.type == "number":
            text = node.text.decode("utf8")
            if "." in text:
                return FloatLiteral(float(text))
            return IntLiteral(int(text))
        elif node.type == "string":
            return StringLiteral(node.text.decode("utf8").strip("'\""))
        elif node.type == "true":
            return BoolLiteral(True)
        elif node.type == "false":
            return BoolLiteral(False)
        elif node.type == "null":
            return NullLiteral()
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
                elif op_str == "==" or op_str == "===":
                    op = BinOp.EQ
                elif op_str == "!=" or op_str == "!==":
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
