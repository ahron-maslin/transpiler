import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node
from transpiler.ir.nodes import *
from transpiler.ir.types import *
from typing import Optional

C_LANGUAGE = Language(tsc.language())

class CFrontend:
    def __init__(self):
        self.parser = Parser(C_LANGUAGE)
        
    def parse(self, source_code: str) -> Program:
        tree = self.parser.parse(bytes(source_code, "utf8"))
        return self._visit_program(tree.root_node)
        
    def _visit_program(self, node: Node) -> Program:
        program = Program()
        for child in node.children:
            if child.type == "function_definition":
                program.functions.append(self._visit_function(child))
        return program
        
    def _visit_function(self, node: Node) -> Function:
        declarator = node.child_by_field_name("declarator")
        body_node = node.child_by_field_name("body")
        type_node = node.child_by_field_name("type")
        
        name = ""
        params = []
        if declarator and declarator.type == "function_declarator":
            name_node = declarator.child_by_field_name("declarator")
            if name_node: name = name_node.text.decode("utf8")
            
            params_node = declarator.child_by_field_name("parameters")
            if params_node:
                for child in params_node.children:
                    if child.type == "parameter_declaration":
                        ptype_node = child.child_by_field_name("type")
                        pdecl_node = child.child_by_field_name("declarator")
                        if pdecl_node and pdecl_node.type == "identifier":
                            pname = pdecl_node.text.decode("utf8")
                            ptype = self._parse_type(ptype_node.text.decode("utf8")) if ptype_node else AnyType
                            params.append(Param(name=pname, type=ptype))
                            
        ret_type = self._parse_type(type_node.text.decode("utf8")) if type_node else VoidType
        body = self._visit_block(body_node) if body_node else Block()
        
        return Function(name=name, params=params, return_type=ret_type, body=body)
        
    def _parse_type(self, type_str: str) -> Type:
        if type_str == "int": return IntType
        if type_str == "double" or type_str == "float": return FloatType
        if type_str == "bool": return BoolType
        if type_str == "char*": return StringType
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
        elif node.type == "declaration":
            type_node = node.child_by_field_name("type")
            typ = self._parse_type(type_node.text.decode("utf8")) if type_node else AnyType
            for child in node.children:
                if child.type == "init_declarator":
                    name_node = child.child_by_field_name("declarator")
                    val_node = child.child_by_field_name("value")
                    name = name_node.text.decode("utf8") if name_node else ""
                    val = self._visit_expr(val_node) if val_node else NullLiteral()
                    return Let(name=name, type=typ, value=val)
        return None
        
    def _visit_expr(self, node: Node) -> Expr:
        if node.type == "number_literal":
            text = node.text.decode("utf8")
            if "." in text: return FloatLiteral(float(text))
            return IntLiteral(int(text))
        elif node.type == "string_literal":
            return StringLiteral(node.text.decode("utf8").strip('"'))
        elif node.type == "true": return BoolLiteral(True)
        elif node.type == "false": return BoolLiteral(False)
        elif node.type == "null": return NullLiteral()
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
