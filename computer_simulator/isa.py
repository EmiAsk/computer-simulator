from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Opcode(Enum):
    LD: int = 0
    ST: int = 1
    ADD: int = 2
    SUB: int = 3
    LT: int = 4
    GT: int = 5
    EQ: int = 6
    MOD: int = 7
    DIV: int = 8
    MUL: int = 9
    JZ: int = 10
    JNZ: int = 11
    JMP: int = 12
    POP: int = 13
    PUSH: int = 14
    CALL: int = 15
    RET: int = 16
    IN: int = 17
    OUT: int = 18
    HLT: int = 19

    def __str__(self) -> str:
        return self.name


class ArgType(Enum):
    IMMEDIATE: int = 0
    REGISTER: int = 1
    ADDRESS: int = 2
    INDIRECT: int = 3
    STACK_OFFSET: int = 4
    PORT: int = 5

    def __str__(self) -> str:
        return self.name


@dataclass
class Arg:
    value: int
    arg_type: ArgType

    def __str__(self) -> str:
        return f"{self.arg_type}={self.value}"

    @property
    def mnemonic(self) -> str:
        if self.arg_type == ArgType.ADDRESS:
            return f"mem[{hex(self.value)}]"
        if self.arg_type == ArgType.PORT:
            return f"port[{hex(self.value)}]"
        if self.arg_type == ArgType.REGISTER:
            return f"r{self.value}"
        if self.arg_type == ArgType.IMMEDIATE:
            return f"{hex(self.value)}"
        if self.arg_type == ArgType.STACK_OFFSET:
            return f"mem[SP {'+' if self.value >= 0 else '-'} {hex(self.value)}]"
        if self.arg_type == ArgType.INDIRECT:
            return f"mem[mem[{hex(self.value)}]]"
        return ""


@dataclass
class Instruction:
    opcode: Opcode
    args: list[Arg] | None
    comment: str | None = None

    def __str__(self) -> str:
        r = f"{self.opcode}"
        if self.args:
            args = ", ".join(map(str, self.args))
            r += f" args[{args}]"
        if self.comment:
            r += f" ({self.comment})"
        return r

    @property
    def mnemonic(self) -> str:
        r = f"{self.opcode} "
        if self.args:
            r += ", ".join([arg.mnemonic for arg in self.args])
        return r
