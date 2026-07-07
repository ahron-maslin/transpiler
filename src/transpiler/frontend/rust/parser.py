import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

RUST_LANGUAGE = Language(tsrust.language())


class RustFrontend:
    def __init__(self):
        self.parser = Parser(RUST_LANGUAGE)

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
                elif expr_node.type == "break_expression":
                    return Break()
                elif expr_node.type == "continue_expression":
                    return Continue()
                elif expr_node.type in (
                    "while_expression",
                    "loop_expression",
                    "for_expression",
                    "if_expression",
                ):
                    return self._visit_stmt(expr_node)
                return ExprStmt(expr=self._visit_expr(expr_node))
        elif node.type == "return_expression":
            val = None
            for child in node.children:
                if child.is_named:
                    val = self._visit_expr(child)
                    break
            return Return(value=val)
        elif node.type == "break_expression":
            return Break()
        elif node.type == "continue_expression":
            return Continue()
        elif node.type == "if_expression":
            cond_node = node.child_by_field_name("condition")
            then_node = node.child_by_field_name("consequence")
            else_node = node.child_by_field_name("alternative")
            cond = self._visit_expr(cond_node) if cond_node else BoolLiteral(True)
            then_block = self._visit_block(then_node) if then_node else Block()
            else_block = self._visit_else_clause(else_node) if else_node else None
            return If(condition=cond, then_block=then_block, else_block=else_block)
        elif node.type == "while_expression":
            cond_node = node.child_by_field_name("condition")
            body_node = node.child_by_field_name("body")
            cond = self._visit_expr(cond_node) if cond_node else BoolLiteral(True)
            body = self._visit_block(body_node) if body_node else Block()
            return While(condition=cond, body=body)
        elif node.type == "loop_expression":
            body_node = node.child_by_field_name("body")
            body = self._visit_block(body_node) if body_node else Block()
            return While(condition=BoolLiteral(True), body=body)
        elif node.type == "for_expression":
            pattern_node = node.child_by_field_name("pattern")
            value_node = node.child_by_field_name("value")
            body_node = node.child_by_field_name("body")
            body = self._visit_block(body_node) if body_node else Block()
            if (
                pattern_node is not None
                and pattern_node.type == "identifier"
                and value_node is not None
                and value_node.type == "range_expression"
            ):
                named = [c for c in value_node.children if c.is_named]
                if len(named) == 2:
                    inclusive = any(
                        (not c.is_named) and c.type == "..=" for c in value_node.children
                    )
                    var_name = pattern_node.text.decode("utf8")
                    start_expr = self._visit_expr(named[0])
                    end_expr = self._visit_expr(named[1])
                    cmp_op = BinOp.LTE if inclusive else BinOp.LT
                    init = Let(name=var_name, type=AnyType, value=start_expr)
                    cond = Binary(op=cmp_op, left=Var(var_name), right=end_expr)
                    update = Assign(
                        target=Var(var_name),
                        value=Binary(op=BinOp.ADD, left=Var(var_name), right=IntLiteral(1)),
                    )
                    return For(init=init, condition=cond, update=update, body=body)
            raise NotImplementedError("RustFrontend: unsupported for-loop over non-range iterable")
        elif node.type in ("line_comment", "block_comment"):
            return None
        elif node.is_named:
            # check if it's the last expression in block (implicit return)
            # but we just wrap in ExprStmt for MVP
            return ExprStmt(expr=self._visit_expr(node))

        return None

    def _visit_else_clause(self, node: Node) -> Block:
        for child in node.children:
            if child.type == "block":
                return self._visit_block(child)
            if child.type == "if_expression":
                stmt = self._visit_stmt(child)
                return Block(statements=[stmt] if stmt else [])
        return Block()

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
        elif node.type == "parenthesized_expression":
            for child in node.children:
                if child.is_named:
                    return self._visit_expr(child)
        elif node.type == "unary_expression":
            arg_node = next((c for c in node.children if c.is_named), None)
            op_text = node.children[0].text.decode("utf8") if node.children else ""
            if arg_node:
                un_op = UnOp.NOT if op_text == "!" else UnOp.NEG
                return Unary(op=un_op, expr=self._visit_expr(arg_node))
        raise NotImplementedError(f"RustFrontend: unsupported expression {node.type}")
