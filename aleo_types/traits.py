from enum import IntEnum
from typing import Protocol, runtime_checkable, Self, Type as TType

from .utils import *


class Deserialize(Protocol):

    @classmethod
    def load(cls, data: BytesIO) -> Self:
        ...


class Serialize(Protocol):

    def dump(self) -> bytes:
        ...


@runtime_checkable
class Serializable(Serialize, Deserialize, Protocol):
    pass


class Sized(Protocol):
    size: int

@runtime_checkable
class Equal(Protocol):
    def __eq__(self, other: Any) -> bool:
        ...

@runtime_checkable
class Compare(Equal, Protocol):
    def __lt__(self, other: Any) -> bool:
        ...

    def __gt__(self, other: Any) -> bool:
        ...

    def __le__(self, other: Any) -> bool:
        ...

    def __ge__(self, other: Any) -> bool:
        ...


@runtime_checkable
class Abs(Protocol):
    def __abs__(self) -> Self:
        ...

@runtime_checkable
class AbsWrapped(Abs, Protocol):
    def abs_wrapped(self) -> Self:
        ...

@runtime_checkable
class Add(Protocol):
    def __add__(self, other: Any) -> Self:
        ...

@runtime_checkable
class AddWrapped(Add, Protocol):
    def add_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Sub(Protocol):
    def __sub__(self, other: Any) -> Self:
        ...

@runtime_checkable
class SubWrapped(Sub, Protocol):
    def sub_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Mul(Protocol):
    def __mul__(self, other: Any) -> Self:
        ...

@runtime_checkable
class MulWrapped(Mul, Protocol):
    def mul_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Div(Protocol):
    def __floordiv__(self, other: Any) -> Self:
        ...

@runtime_checkable
class DivWrapped(Div, Protocol):
    def div_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class And(Protocol):
    def __and__(self, other: Any) -> Self:
        ...

@runtime_checkable
class Or(Protocol):
    def __or__(self, other: Any) -> Self:
        ...

@runtime_checkable
class Xor(Protocol):
    def __xor__(self, other: Any) -> Self:
        ...

@runtime_checkable
class Not(Protocol):
    def __invert__(self) -> Self:
        ...

@runtime_checkable
class Nand(Protocol):
    def nand(self, other: Any) -> Self:
        ...

@runtime_checkable
class Nor(Protocol):
    def nor(self, other: Any) -> Self:
        ...

@runtime_checkable
class Shl(Protocol):
    def __lshift__(self, other: Any) -> Self:
        ...

@runtime_checkable
class ShlWrapped(Shl, Protocol):
    def shl_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Shr(Protocol):
    def __rshift__(self, other: Any) -> Self:
        ...

@runtime_checkable
class ShrWrapped(Shr, Protocol):
    def shr_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Rem(Protocol):
    def __mod__(self, other: Any) -> Self:
        ...

@runtime_checkable
class RemWrapped(Rem, Protocol):
    def rem_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Pow(Protocol):
    def __pow__(self, other: Any) -> Self:
        ...

@runtime_checkable
class PowWrapped(Pow, Protocol):
    def pow_wrapped(self, other: Any) -> Self:
        ...

@runtime_checkable
class Double(Add, Protocol):
    def double(self) -> Self:
        ...

@runtime_checkable
class Square(Mul, Protocol):
    def square(self) -> Self:
        ...

@runtime_checkable
class Sqrt(Protocol):
    def sqrt(self) -> Self:
        ...

@runtime_checkable
class Inv(Protocol):
    def inv(self) -> Self:
        ...

@runtime_checkable
class Mod(Protocol):
    def __mod__(self, other: Any) -> Self:
        ...

@runtime_checkable
class Neg(Protocol):
    def __neg__(self) -> Self:
        ...

@runtime_checkable
class Cast(Protocol):
    def cast(self, destination_type: Any, *, lossy: bool) -> Any:
        ...

class RustEnum(Protocol):
    Type: TType[IntEnum]

class EnumBaseSerialize(Serialize):

    def dump(self) -> bytes:
        raise TypeError("cannot serialize base class")
