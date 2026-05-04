import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

JAVA_LANGUAGE = Language(tsjava.language())

class JavaFrontend:
    def __init__(self):
        self.parser = Parser(JAVA_LANGUAGE)
        
    def parse(self, source_code: str) -> Program:
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return self._visit_program(tree.root_node)
        
    def _visit_program(self, node: Node) -> Program:
        program = Program()
        for child in node.children:
            if child.type == "class_declaration":
                body = child.child_by_field_name("body")
                if body:
                    for method_node in body.children:
                        if method_node.type == "method_declaration":
                            program.functions.append(self._visit_function(method_node))
        return program
        
    def _visit_function(self, node: Node) -> Function:
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        body_node = node.child_by_field_name("body")
        type_node = node.child_by_field_name("type")
        
        name = name_node.text.decode("utf8") if name_node else ""
        
        params = []
        if params_node:
            for child in params_node.children:
                if child.type == "formal_parameter":
                    pname_node = child.child_by_field_name("name")
                    ptype_node = child.child_by_field_name("type")
                    if pname_node:
                        pname = pname_node.text.decode("utf8")
                        ptype = self._parse_type(ptype_node.text.decode("utf8")) if ptype_node else AnyType
                        params.append(Param(name=pname, type=ptype))
                        
        ret_type = self._parse_type(type_node.text.decode("utf8")) if type_node else VoidType
        body = self._visit_block(body_node) if body_node else Block()
        
        return Function(name=name, params=params, return_type=ret_type, body=body)
        
    def _parse_type(self, type_str: str) -> Type:
        if type_str == "int" or type_str == "long": return IntType
        if type_str == "double" or type_str == "float": return FloatType
        if type_str == "boolean": return BoolType
        if type_str == "String": return StringType
        if type_str == "void": return VoidType
        return AnyType

    def _visit_block(self, node: Node) -> Block:
        stmts = []
        for child in node.children:
            if child.is_named:
                stmt = self._visit_stmt(child)
                if stmt: stmts.append(stmt)
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
            for child in node.children:
                if child.is_named:
                    if child.type == "assignment_expression":
                        left = child.child_by_field_name("left")
                        right = child.child_by_field_name("right")
                        if left and right:
                            return Assign(target=self._visit_expr(left), value=self._visit_expr(right))
                    return ExprStmt(expr=self._visit_expr(child))
        elif node.type == "local_variable_declaration":
            type_node = node.child_by_field_name("type")
            typ = self._parse_type(type_node.text.decode("utf8")) if type_node else AnyType
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    val_node = child.child_by_field_name("value")
                    name = name_node.text.decode("utf8") if name_node else ""
                    val = self._visit_expr(val_node) if val_node else NullLiteral()
                    return Let(name=name, type=typ, value=val)
        return None
        
    def _visit_expr(self, node: Node) -> Expr:
        if node.type == "decimal_integer_literal":
            return IntLiteral(int(node.text.decode("utf8")))
        elif node.type == "decimal_floating_point_literal":
            return FloatLiteral(float(node.text.decode("utf8")))
        elif node.type == "string_literal":
            return StringLiteral(node.text.decode("utf8").strip('"'))
        elif node.type == "true": return BoolLiteral(True)
        elif node.type == "false": return BoolLiteral(False)
        elif node.type == "null_literal": return NullLiteral()
        elif node.type == "identifier":
            return Var(node.text.decode("utf8"))
        elif node.type == "binary_expression":
            left_node = node.child_by_field_name("left")
            right_node = node.child_by_field_name("right")
            op_node = node.child_by_field_name("operator")
            
            if left_node and right_node and op_node:
                op_str = op_node.text.decode("utf8")
                op = None
                if op_str == "+": op = BinOp.ADD
                elif op_str == "-": op = BinOp.SUB
                elif op_str == "*": op = BinOp.MUL
                elif op_str == "/": op = BinOp.DIV
                elif op_str == "%": op = BinOp.MOD
                elif op_str == "==": op = BinOp.EQ
                elif op_str == "!=": op = BinOp.NEQ
                elif op_str == "<": op = BinOp.LT
                elif op_str == "<=": op = BinOp.LTE
                elif op_str == ">": op = BinOp.GT
                elif op_str == ">=": op = BinOp.GTE
                elif op_str == "&&": op = BinOp.AND
                elif op_str == "||": op = BinOp.OR
                
                if op:
                    return Binary(op=op, left=self._visit_expr(left_node), right=self._visit_expr(right_node))
        return NullLiteral()
