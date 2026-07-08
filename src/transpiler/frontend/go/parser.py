import tree_sitter_go as tsgo
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import List, Optional

GO_LANGUAGE = Language(tsgo.language())


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
                        stmts.extend(self._visit_stmt_multi(stmt_child))
            elif child.is_named and child.type != "statement_list":
                stmts.extend(self._visit_stmt_multi(child))
        return Block(statements=stmts)

    def _visit_stmt_multi(self, node: Node) -> List[Stmt]:
        if node.type in ("short_var_declaration", "assignment_statement"):
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and right:
                names = [c for c in left.children if c.is_named]
                vals = [c for c in right.children if c.is_named]
                is_decl = node.type == "short_var_declaration"
                if len(names) == 1 and len(vals) == 1:
                    value = self._visit_expr(vals[0])
                    if is_decl:
                        return [Let(name=names[0].text.decode("utf8"), type=AnyType, value=value)]
                    return [Assign(target=self._visit_expr(names[0]), value=value)]
                # Go evaluates all RHS values before any target is bound (needed for
                # correctness of e.g. `a, b = b, a`); stage through temporaries.
                stmts: List[Stmt] = []
                temp_names = []
                for idx, v in enumerate(vals):
                    temp_name = f"__go_multi_tmp_{id(node)}_{idx}"
                    stmts.append(Let(name=temp_name, type=AnyType, value=self._visit_expr(v)))
                    temp_names.append(temp_name)
                for n, temp_name in zip(names, temp_names):
                    if is_decl:
                        stmts.append(
                            Let(name=n.text.decode("utf8"), type=AnyType, value=Var(temp_name))
                        )
                    else:
                        stmts.append(Assign(target=self._visit_expr(n), value=Var(temp_name)))
                return stmts
        stmt = self._visit_stmt(node)
        return [stmt] if stmt else []

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
        elif node.type == "var_declaration":
            for child in node.children:
                if child.type == "var_spec":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    type_node = child.child_by_field_name("type")
                    name = name_node.text.decode("utf8") if name_node else ""

                    val = NullLiteral()
                    if val_node:
                        for e_child in val_node.children:
                            if e_child.is_named:
                                val = self._visit_expr(e_child)
                                break

                    typ = self._parse_type(type_node.text.decode("utf8")) if type_node else AnyType
                    return Let(name=name, type=typ, value=val)
        elif node.type == "if_statement":
            cond_node = node.child_by_field_name("condition")
            then_node = node.child_by_field_name("consequence")
            else_node = node.child_by_field_name("alternative")
            cond = self._visit_expr(cond_node) if cond_node else BoolLiteral(True)
            then_block = self._visit_block(then_node) if then_node else Block()
            else_block = self._visit_block(else_node) if else_node else None
            return If(condition=cond, then_block=then_block, else_block=else_block)
        elif node.type == "for_statement":
            body_node = node.child_by_field_name("body")
            body = self._visit_block(body_node) if body_node else Block()

            for_clause = None
            cond_node = None
            for child in node.children:
                if child.type == "for_clause":
                    for_clause = child
                elif child.is_named and child.type != "block":
                    cond_node = child

            if for_clause:
                init_node = for_clause.child_by_field_name("initializer")
                clause_cond_node = for_clause.child_by_field_name("condition")
                update_node = for_clause.child_by_field_name("update")
                init_stmts = self._visit_stmt_multi(init_node) if init_node else []
                init_stmt = init_stmts[0] if len(init_stmts) == 1 else Block(statements=init_stmts)
                cond = self._visit_expr(clause_cond_node) if clause_cond_node else BoolLiteral(True)
                update_stmts = self._visit_stmt_multi(update_node) if update_node else []
                update_stmt = (
                    update_stmts[0] if len(update_stmts) == 1 else Block(statements=update_stmts)
                )
                return For(init=init_stmt, condition=cond, update=update_stmt, body=body)
            elif cond_node:
                return While(condition=self._visit_expr(cond_node), body=body)
            else:
                return While(condition=BoolLiteral(True), body=body)
        elif node.type == "inc_statement" or node.type == "dec_statement":
            target = next((c for c in node.children if c.is_named), None)
            if target:
                var = self._visit_expr(target)
                op = BinOp.ADD if node.type == "inc_statement" else BinOp.SUB
                return Assign(target=var, value=Binary(op=op, left=var, right=IntLiteral(1)))
        elif node.type == "break_statement":
            return Break()
        elif node.type == "continue_statement":
            return Continue()
        elif node.type == "comment":
            return None
        raise NotImplementedError(f"GoFrontend: unsupported statement {node.type}")

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
        elif node.type == "parenthesized_expression":
            for child in node.children:
                if child.is_named:
                    return self._visit_expr(child)
        elif node.type == "unary_expression":
            op_node = node.child_by_field_name("operator")
            arg_node = next((c for c in node.children if c.is_named), None)
            if op_node and arg_node:
                op_str = op_node.text.decode("utf8")
                un_op = UnOp.NOT if op_str == "!" else UnOp.NEG
                return Unary(op=un_op, expr=self._visit_expr(arg_node))
        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")
            func = self._visit_expr(func_node) if func_node else NullLiteral()
            args = (
                [self._visit_expr(c) for c in args_node.children if c.is_named] if args_node else []
            )
            return Call(function=func, args=args)
        elif node.type == "selector_expression":
            operand_node = node.child_by_field_name("operand")
            field_node = node.child_by_field_name("field")
            if operand_node and field_node:
                return FieldAccess(
                    object=self._visit_expr(operand_node), field=field_node.text.decode("utf8")
                )
        raise NotImplementedError(f"GoFrontend: unsupported expression {node.type}")
