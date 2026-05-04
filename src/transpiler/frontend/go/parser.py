import tree_sitter_go as tsgo
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

GO_LANGUAGE = Language(tsgo.language(), "go")


class GoFrontend:
    def __init__(self):
        self.parser = Parser(GO_LANGUAGE)

    def parse(self, source_code: str) -> Program:
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return self._visit_program(tree.root_node)

    def _visit_program(self, node: Node) -> Program:
        program = Program()
        for child in node.children:
            if child.type == "function_declaration":
                program.functions.append(self._visit_function(child))
        return program

    def _visit_function(self, node: Node) -> Function:
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        body_node = node.child_by_field_name("body")
        ret_node = node.child_by_field_name("result")

        name = name_node.text.decode("utf8") if name_node else ""

        params = []
        if params_node:
            for child in params_node.children:
                if child.type == "parameter_declaration":
                    pname_node = child.child_by_field_name("name")
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
        if type_str == "int" or type_str == "int32" or type_str == "int64":
            return IntType
        if type_str == "float32" or type_str == "float64":
            return FloatType
        if type_str == "bool":
            return BoolType
        if type_str == "string":
            return StringType
        return AnyType

    def _visit_block(self, node: Node) -> Block:
        stmts = []
        for child in node.children:
            if child.type == "statement_list":
                for stmt_child in child.children:
                    if stmt_child.is_named:
                        stmt = self._visit_stmt(stmt_child)
                        if stmt:
                            stmts.append(stmt)
            elif child.is_named and child.type != "statement_list":
                stmt = self._visit_stmt(child)
                if stmt:
                    stmts.append(stmt)
        return Block(statements=stmts)

    def _visit_stmt(self, node: Node) -> Optional[Stmt]:
        if node.type == "return_statement":
            value = None
            for child in node.children:
                if child.type == "expression_list":
                    for e_child in child.children:
                        if e_child.is_named:
                            value = self._visit_expr(e_child)
                            break
            return Return(value=value)
        elif node.type == "expression_statement":
            expr_node = None
            for child in node.children:
                if child.is_named:
                    expr_node = child
                    break
            if expr_node:
                return ExprStmt(expr=self._visit_expr(expr_node))
        elif node.type == "short_var_declaration":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and right:
                # Need to handle expression list, but we take first child for MVP
                name_child = left.children[0] if left.children else None
                val_child = right.children[0] if right.children else None
                if name_child and val_child:
                    name = name_child.text.decode("utf8")
                    val = self._visit_expr(val_child)
                    return Let(name=name, type=AnyType, value=val)
        elif node.type == "assignment_statement":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and right:
                l_child = left.children[0] if left.children else None
                r_child = right.children[0] if right.children else None
                if l_child and r_child:
                    return Assign(target=self._visit_expr(l_child), value=self._visit_expr(r_child))
        elif node.type == "var_declaration":
            for child in node.children:
                if child.type == "var_spec":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    type_node = child.child_by_field_name("type")
                    name = name_node.text.decode("utf8") if name_node else ""
                    val = self._visit_expr(val_node) if val_node else NullLiteral()
                    typ = self._parse_type(type_node.text.decode("utf8")) if type_node else AnyType
                    return Let(name=name, type=typ, value=val)
        return None

    def _visit_expr(self, node: Node) -> Expr:
        if node.type == "int_literal":
            return IntLiteral(int(node.text.decode("utf8")))
        elif node.type == "float_literal":
            return FloatLiteral(float(node.text.decode("utf8")))
        elif node.type == "interpreted_string_literal":
            return StringLiteral(node.text.decode("utf8").strip('"'))
        elif node.type == "true":
            return BoolLiteral(True)
        elif node.type == "false":
            return BoolLiteral(False)
        elif node.type == "nil":
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
