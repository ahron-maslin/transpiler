from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from ir.types import Type

class ASTNode:
    pass

class Expr(ASTNode):
    pass

class Stmt(ASTNode):
    pass

# Literals
@dataclass
class Literal(Expr):
    pass

@dataclass
class IntLiteral(Literal):
    value: int

@dataclass
class FloatLiteral(Literal):
    value: float

@dataclass
class BoolLiteral(Literal):
    value: bool

@dataclass
class StringLiteral(Literal):
    value: str

@dataclass
class NullLiteral(Literal):
    pass

# Expressions
@dataclass
class Var(Expr):
    name: str

class BinOp(Enum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"
    EQ = "=="
    NEQ = "!="
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="
    AND = "&&"
    OR = "||"

@dataclass
class Binary(Expr):
    op: BinOp
    left: Expr
    right: Expr

class UnOp(Enum):
    NEG = "-"
    NOT = "!"

@dataclass
class Unary(Expr):
    op: UnOp
    expr: Expr

@dataclass
class Call(Expr):
    function: Expr
    args: List[Expr]

@dataclass
class FieldAccess(Expr):
    object: Expr
    field: str

@dataclass
class IndexAccess(Expr):
    collection: Expr
    index: Expr

@dataclass
class StructInit(Expr):
    name: str
    fields: Dict[str, Expr]

@dataclass
class ArrayInit(Expr):
    elements: List[Expr]

@dataclass
class MapInit(Expr):
    entries: List[Tuple[Expr, Expr]]

@dataclass
class Cast(Expr):
    expr: Expr
    target_type: Type

# Statements
@dataclass
class Block(Stmt):
    statements: List[Stmt] = field(default_factory=list)

@dataclass
class Let(Stmt):
    name: str
    type: Type
    value: Expr

@dataclass
class Assign(Stmt):
    target: Expr
    value: Expr

@dataclass
class If(Stmt):
    condition: Expr
    then_block: Block
    else_block: Optional[Block] = None

@dataclass
class While(Stmt):
    condition: Expr
    body: Block

@dataclass
class For(Stmt):
    init: Stmt
    condition: Expr
    update: Stmt
    body: Block

@dataclass
class Return(Stmt):
    value: Optional[Expr] = None

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class Break(Stmt):
    pass

@dataclass
class Continue(Stmt):
    pass

# Top level
@dataclass
class Param:
    name: str
    type: Type

@dataclass
class Function(ASTNode):
    name: str
    params: List[Param]
    return_type: Type
    body: Block

@dataclass
class Struct(ASTNode):
    name: str
    fields: List[Tuple[str, Type]]

@dataclass
class GlobalVar(ASTNode):
    name: str
    type: Type
    value: Optional[Expr]

@dataclass
class Program(ASTNode):
    functions: List[Function] = field(default_factory=list)
    structs: List[Struct] = field(default_factory=list)
    globals: List[GlobalVar] = field(default_factory=list)
