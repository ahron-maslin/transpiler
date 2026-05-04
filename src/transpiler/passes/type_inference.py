from typing import Dict
from transpiler.ir.nodes import *
from transpiler.ir.types import *


class TypeInferencePass:
    def __init__(self):
        self.env: Dict[str, Type] = {}
        self.functions: Dict[str, Function] = {}

    def execute(self, program: Program):
        for func in program.functions:
            self.functions[func.name] = func

        for function in program.functions:
            self.env.clear()
            for p in function.params:
                self.env[p.name] = p.type
            self._infer_function(function)

    def _infer_function(self, node: Function):
        self._infer_block(node.body)

    def _infer_block(self, node: Block):
        for stmt in node.statements:
            self._infer_stmt(stmt)

    def _infer_stmt(self, node: Stmt):
        if isinstance(node, Let):
            inferred_type = self._infer_expr_type(node.value)
            if (
                node.type.kind == TypeKind.ANY
                and inferred_type
                and inferred_type.kind != TypeKind.ANY
            ):
                node.type = inferred_type
            self.env[node.name] = node.type

        elif isinstance(node, Assign):
            pass
        elif isinstance(node, If):
            self._infer_block(node.then_block)
            if node.else_block:
                self._infer_block(node.else_block)
        elif isinstance(node, While):
            self._infer_block(node.body)
        elif isinstance(node, For):
            self._infer_stmt(node.init)
            self._infer_stmt(node.update)
            self._infer_block(node.body)

    def _infer_expr_type(self, node: Expr) -> Type:
        if isinstance(node, IntLiteral):
            return IntType
        elif isinstance(node, FloatLiteral):
            return FloatType
        elif isinstance(node, BoolLiteral):
            return BoolType
        elif isinstance(node, StringLiteral):
            return StringType
        elif isinstance(node, NullLiteral):
            return AnyType
        elif isinstance(node, Var):
            return self.env.get(node.name, AnyType)
        elif isinstance(node, Binary):
            if node.op in [
                BinOp.EQ,
                BinOp.NEQ,
                BinOp.LT,
                BinOp.LTE,
                BinOp.GT,
                BinOp.GTE,
                BinOp.AND,
                BinOp.OR,
            ]:
                return BoolType
            left_type = self._infer_expr_type(node.left)
            right_type = self._infer_expr_type(node.right)
            if left_type.kind != TypeKind.ANY:
                return left_type
            if right_type.kind != TypeKind.ANY:
                return right_type
            return AnyType
        elif isinstance(node, Call):
            if isinstance(node.function, Var) and node.function.name in self.functions:
                return self.functions[node.function.name].return_type
            return AnyType
        elif isinstance(node, FieldAccess):
            return AnyType
        return AnyType
