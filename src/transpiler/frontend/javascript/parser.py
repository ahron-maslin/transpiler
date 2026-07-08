import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

JS_LANGUAGE = Language(tsjavascript.language())


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
        elif node.type == "if_statement":
            cond_node = node.child_by_field_name("condition")
            then_node = node.child_by_field_name("consequence")
            else_node = node.child_by_field_name("alternative")
            cond = self._visit_expr(cond_node) if cond_node else BoolLiteral(True)
            if hasattr(cond_node, "type") and cond_node.type == "parenthesized_expression":
                for child in cond_node.children:
                    if child.is_named:
                        cond = self._visit_expr(child)
                        break
            then_block = self._visit_block(then_node) if then_node else Block()
            else_block = self._visit_else_clause(else_node) if else_node else None
            return If(condition=cond, then_block=then_block, else_block=else_block)
        elif node.type == "while_statement":
            cond_node = node.child_by_field_name("condition")
            body_node = node.child_by_field_name("body")
            cond = self._visit_expr(cond_node) if cond_node else BoolLiteral(True)
            if hasattr(cond_node, "type") and cond_node.type == "parenthesized_expression":
                for child in cond_node.children:
                    if child.is_named:
                        cond = self._visit_expr(child)
                        break
            body = self._visit_block(body_node) if body_node else Block()
            return While(condition=cond, body=body)
        elif node.type == "for_statement":
            init_node = node.child_by_field_name("initializer")
            cond_node = node.child_by_field_name("condition")
            update_node = node.child_by_field_name("increment")
            body_node = node.child_by_field_name("body")
            init_stmt = self._visit_for_clause_stmt(init_node) if init_node else Block()
            cond = self._visit_expr(cond_node) if cond_node else BoolLiteral(True)
            update_stmt = self._visit_for_clause_stmt(update_node) if update_node else Block()
            body = self._visit_block(body_node) if body_node else Block()
            return For(init=init_stmt, condition=cond, update=update_stmt, body=body)
        elif node.type == "break_statement":
            return Break()
        elif node.type == "continue_statement":
            return Continue()
        elif node.type == "comment":
            return None
        raise NotImplementedError(f"JSFrontend: unsupported statement {node.type}")

    def _visit_else_clause(self, node: Node) -> Block:
        if node.type == "else_clause":
            for child in node.children:
                if child.type == "if_statement":
                    stmt = self._visit_stmt(child)
                    return Block(statements=[stmt] if stmt else [])
                if child.is_named:
                    return self._visit_block(child)
            return Block()
        return self._visit_block(node)

    def _visit_for_clause_stmt(self, node: Node) -> Stmt:
        if node.type == "update_expression":
            arg_node = node.child_by_field_name("argument")
            op_node = node.child_by_field_name("operator")
            if arg_node and op_node:
                var = self._visit_expr(arg_node)
                op = BinOp.ADD if op_node.text.decode("utf8") == "++" else BinOp.SUB
                return Assign(target=var, value=Binary(op=op, left=var, right=IntLiteral(1)))
        elif node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and right:
                return Assign(target=self._visit_expr(left), value=self._visit_expr(right))
        elif node.type in ("lexical_declaration", "variable_declaration"):
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    name = name_node.text.decode("utf8") if name_node else ""
                    val = self._visit_expr(val_node) if val_node else NullLiteral()
                    return Let(name=name, type=AnyType, value=val)
        return ExprStmt(expr=self._visit_expr(node))

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
        elif node.type == "parenthesized_expression":
            for child in node.children:
                if child.is_named:
                    return self._visit_expr(child)
        elif node.type == "unary_expression":
            op_node = node.child_by_field_name("operator")
            arg_node = node.child_by_field_name("argument")
            if op_node and arg_node:
                un_op = UnOp.NOT if op_node.text.decode("utf8") == "!" else UnOp.NEG
                return Unary(op=un_op, expr=self._visit_expr(arg_node))
        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")
            func = self._visit_expr(func_node) if func_node else NullLiteral()
            args = (
                [self._visit_expr(c) for c in args_node.children if c.is_named] if args_node else []
            )
            return Call(function=func, args=args)
        elif node.type == "member_expression":
            object_node = node.child_by_field_name("object")
            property_node = node.child_by_field_name("property")
            if object_node and property_node:
                return FieldAccess(
                    object=self._visit_expr(object_node), field=property_node.text.decode("utf8")
                )
        raise NotImplementedError(f"JSFrontend: unsupported expression {node.type}")
