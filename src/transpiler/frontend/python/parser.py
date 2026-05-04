import ast
from typing import List, Optional
from transpiler.ir.nodes import *
from transpiler.ir.types import *


class PythonFrontend:
    def parse(self, source_code: str) -> Program:
        tree = ast.parse(source_code)
        return self._visit_program(tree)

    def _visit_program(self, node: ast.Module) -> Program:
        program = Program()
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                program.functions.append(self._visit_function(stmt))
            elif isinstance(stmt, ast.ClassDef):
                program.structs.append(self._visit_struct(stmt))
            elif isinstance(stmt, ast.Assign):
                pass  # global assign ignored for MVP
        return program

    def _visit_function(self, node: ast.FunctionDef) -> Function:
        params = []
        for arg in node.args.args:
            param_type = AnyType
            if arg.annotation:
                param_type = self._parse_type(arg.annotation)
            params.append(Param(name=arg.arg, type=param_type))

        ret_type = AnyType
        if node.returns:
            ret_type = self._parse_type(node.returns)

        body = self._visit_block(node.body)
        return Function(name=node.name, params=params, return_type=ret_type, body=body)

    def _visit_struct(self, node: ast.ClassDef) -> Struct:
        fields = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    name = stmt.target.id
                    typ = self._parse_type(stmt.annotation)
                    fields.append((name, typ))
        return Struct(name=node.name, fields=fields)

    def _parse_type(self, node: ast.expr) -> Type:
        if isinstance(node, ast.Name):
            if node.id == "int":
                return IntType
            elif node.id == "float":
                return FloatType
            elif node.id == "bool":
                return BoolType
            elif node.id == "str":
                return StringType
        return AnyType

    def _visit_block(self, nodes: List[ast.stmt]) -> Block:
        stmts = []
        for n in nodes:
            stmt = self._visit_stmt(n)
            if stmt:
                stmts.append(stmt)
        return Block(statements=stmts)

    def _visit_stmt(self, node: ast.stmt) -> Optional[Stmt]:
        if isinstance(node, ast.Return):
            val = None
            if node.value:
                val = self._visit_expr(node.value)
            return Return(value=val)
        elif isinstance(node, ast.Assign):
            if len(node.targets) == 1:
                target = self._visit_expr(node.targets[0])
                value = self._visit_expr(node.value)
                return Assign(target=target, value=value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                name = node.target.id
                typ = self._parse_type(node.annotation)
                val = self._visit_expr(node.value) if node.value else NullLiteral()
                return Let(name=name, type=typ, value=val)
        elif isinstance(node, ast.Expr):
            return ExprStmt(expr=self._visit_expr(node.value))
        elif isinstance(node, ast.If):
            cond = self._visit_expr(node.test)
            then_b = self._visit_block(node.body)
            else_b = self._visit_block(node.orelse) if node.orelse else None
            return If(condition=cond, then_block=then_b, else_block=else_b)
        elif isinstance(node, ast.While):
            cond = self._visit_expr(node.test)
            body = self._visit_block(node.body)
            return While(condition=cond, body=body)
        return None

    def _visit_expr(self, node: ast.expr) -> Expr:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return BoolLiteral(value=node.value)
            elif isinstance(node.value, int):
                return IntLiteral(value=node.value)
            elif isinstance(node.value, float):
                return FloatLiteral(value=node.value)
            elif isinstance(node.value, str):
                return StringLiteral(value=node.value)
            elif node.value is None:
                return NullLiteral()
        elif isinstance(node, ast.Name):
            return Var(name=node.id)
        elif isinstance(node, ast.BinOp):
            op = None
            if isinstance(node.op, ast.Add):
                op = BinOp.ADD
            elif isinstance(node.op, ast.Sub):
                op = BinOp.SUB
            elif isinstance(node.op, ast.Mult):
                op = BinOp.MUL
            elif isinstance(node.op, ast.Div):
                op = BinOp.DIV
            elif isinstance(node.op, ast.Mod):
                op = BinOp.MOD
            left = self._visit_expr(node.left)
            right = self._visit_expr(node.right)
            if op:
                return Binary(op=op, left=left, right=right)
        elif isinstance(node, ast.Compare):
            if len(node.ops) == 1 and len(node.comparators) == 1:
                op = None
                if isinstance(node.ops[0], ast.Eq):
                    op = BinOp.EQ
                elif isinstance(node.ops[0], ast.NotEq):
                    op = BinOp.NEQ
                elif isinstance(node.ops[0], ast.Lt):
                    op = BinOp.LT
                elif isinstance(node.ops[0], ast.LtE):
                    op = BinOp.LTE
                elif isinstance(node.ops[0], ast.Gt):
                    op = BinOp.GT
                elif isinstance(node.ops[0], ast.GtE):
                    op = BinOp.GTE
                left = self._visit_expr(node.left)
                right = self._visit_expr(node.comparators[0])
                if op:
                    return Binary(op=op, left=left, right=right)
        elif isinstance(node, ast.Call):
            func = self._visit_expr(node.func)
            args = [self._visit_expr(arg) for arg in node.args]
            return Call(function=func, args=args)
        elif isinstance(node, ast.Attribute):
            obj = self._visit_expr(node.value)
            return FieldAccess(object=obj, field=node.attr)
        return NullLiteral()
