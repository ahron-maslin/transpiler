from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Union

class TypeKind(Enum):
    VOID = "Void"
    BOOL = "Bool"
    INT = "Int"
    FLOAT = "Float"
    STRING = "String"
    ARRAY = "Array"
    MAP = "Map"
    STRUCT = "Struct"
    FUNCTION = "Function"
    OPTIONAL = "Optional"
    ANY = "Any"

@dataclass
class Type:
    kind: TypeKind

@dataclass
class PrimitiveType(Type):
    pass

# Singletons for primitives
VoidType = PrimitiveType(TypeKind.VOID)
BoolType = PrimitiveType(TypeKind.BOOL)
IntType = PrimitiveType(TypeKind.INT)
FloatType = PrimitiveType(TypeKind.FLOAT)
StringType = PrimitiveType(TypeKind.STRING)
AnyType = PrimitiveType(TypeKind.ANY)

@dataclass
class ArrayType(Type):
    element_type: Type

    def __init__(self, element_type: Type):
        super().__init__(TypeKind.ARRAY)
        self.element_type = element_type

@dataclass
class MapType(Type):
    key_type: Type
    value_type: Type

    def __init__(self, key_type: Type, value_type: Type):
        super().__init__(TypeKind.MAP)
        self.key_type = key_type
        self.value_type = value_type

@dataclass
class StructType(Type):
    name: str

    def __init__(self, name: str):
        super().__init__(TypeKind.STRUCT)
        self.name = name

@dataclass
class FunctionType(Type):
    params: List[Type]
    return_type: Type

    def __init__(self, params: List[Type], return_type: Type):
        super().__init__(TypeKind.FUNCTION)
        self.params = params
        self.return_type = return_type

@dataclass
class OptionalType(Type):
    inner_type: Type

    def __init__(self, inner_type: Type):
        super().__init__(TypeKind.OPTIONAL)
        self.inner_type = inner_type
