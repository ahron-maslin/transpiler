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
                if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    program.globals.append(
                        GlobalVar(
                            name=stmt.targets[0].id,
                            type=AnyType,
                            value=self._visit_expr(stmt.value),
                        )
                    )
            elif isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    typ = self._parse_type(stmt.annotation)
                    value = self._visit_expr(stmt.value) if stmt.value else None
                    program.globals.append(GlobalVar(name=stmt.target.id, type=typ, value=value))
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
            stmts.extend(self._visit_stmt_multi(n))
        return Block(statements=stmts)

    def _visit_stmt_multi(self, node: ast.stmt) -> List[Stmt]:
        if isinstance(node, ast.Assign) and len(node.targets) > 1:
            value = self._visit_expr(node.value)
            return [Assign(target=self._visit_expr(t), value=value) for t in node.targets]
        stmt = self._visit_stmt(node)
        return [stmt] if stmt else []

    _AUGASSIGN_OPS = {
        ast.Add: BinOp.ADD,
        ast.Sub: BinOp.SUB,
        ast.Mult: BinOp.MUL,
        ast.Div: BinOp.DIV,
        ast.Mod: BinOp.MOD,
    }

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
        elif isinstance(node, ast.AugAssign):
            op = self._AUGASSIGN_OPS.get(type(node.op))
            if op is None:
                raise NotImplementedError(f"unsupported augmented assignment operator: {node.op}")
            target = self._visit_expr(node.target)
            value = self._visit_expr(node.value)
            return Assign(target=target, value=Binary(op=op, left=target, right=value))
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
        elif isinstance(node, ast.For):
            return self._visit_for(node)
        elif isinstance(node, ast.Break):
            return Break()
        elif isinstance(node, ast.Continue):
            return Continue()
        elif isinstance(node, ast.Try):
            raise NotImplementedError("PythonFrontend: try/except is not supported")
        elif isinstance(node, ast.With):
            raise NotImplementedError("PythonFrontend: with-statements are not supported")
        elif isinstance(node, ast.Pass):
            return None
        raise NotImplementedError(f"PythonFrontend: unsupported statement {type(node).__name__}")

    def _visit_for(self, node: ast.For) -> For:
        if node.orelse:
            raise NotImplementedError("PythonFrontend: for/else is not supported")
        if not isinstance(node.target, ast.Name):
            raise NotImplementedError("PythonFrontend: only simple for-loop targets are supported")
        if not (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
            and 1 <= len(node.iter.args) <= 3
        ):
            raise NotImplementedError(
                f"PythonFrontend: unsupported for-loop iterable: {ast.dump(node.iter)}"
            )

        var_name = node.target.id
        args = node.iter.args
        if len(args) == 1:
            start, end, step = IntLiteral(0), self._visit_expr(args[0]), IntLiteral(1)
        elif len(args) == 2:
            start, end, step = self._visit_expr(args[0]), self._visit_expr(args[1]), IntLiteral(1)
        else:
            start, end, step = (
                self._visit_expr(args[0]),
                self._visit_expr(args[1]),
                self._visit_expr(args[2]),
            )

        init = Let(name=var_name, type=IntType, value=start)
        condition = Binary(op=BinOp.LT, left=Var(var_name), right=end)
        update = Assign(
            target=Var(var_name), value=Binary(op=BinOp.ADD, left=Var(var_name), right=step)
        )
        body = self._visit_block(node.body)
        return For(init=init, condition=condition, update=update, body=body)

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
        elif isinstance(node, ast.BoolOp):
            op = BinOp.AND if isinstance(node.op, ast.And) else BinOp.OR
            values = [self._visit_expr(v) for v in node.values]
            expr = values[0]
            for v in values[1:]:
                expr = Binary(op=op, left=expr, right=v)
            return expr
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return Unary(op=UnOp.NOT, expr=self._visit_expr(node.operand))
            elif isinstance(node.op, ast.USub):
                return Unary(op=UnOp.NEG, expr=self._visit_expr(node.operand))
            raise NotImplementedError(f"PythonFrontend: unsupported unary operator: {node.op}")
        elif isinstance(node, ast.Subscript):
            collection = self._visit_expr(node.value)
            index_node = node.slice
            return IndexAccess(collection=collection, index=self._visit_expr(index_node))
        elif isinstance(node, ast.Call):
            func = self._visit_expr(node.func)
            args = [self._visit_expr(arg) for arg in node.args]
            return Call(function=func, args=args)
        elif isinstance(node, ast.Attribute):
            obj = self._visit_expr(node.value)
            return FieldAccess(object=obj, field=node.attr)
        raise NotImplementedError(f"PythonFrontend: unsupported expression {type(node).__name__}")
