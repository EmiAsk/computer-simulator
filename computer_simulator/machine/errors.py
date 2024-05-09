from __future__ import annotations

from typing import Any

from computer_simulator.isa import Instruction


class UnknownSignalError(Exception):
    def __init__(self, signal: Any):
        super().__init__(f"Unknown signal: {signal}")


class UnknownStageError(Exception):
    def __init__(self, stage: Any):
        super().__init__(f"Unknown stage: {stage}")


class UnknownOpcodeError(Exception):
    def __init__(self, opcode: Any):
        super().__init__(f"Unknown opcode: {opcode}")


class InvalidArgTypeError(Exception):
    def __init__(self, arg_type: Any):
        super().__init__(f"Invalid arg type: {arg_type}")


class InvalidTickError(Exception):
    def __init__(self, tick: Any):
        super().__init__(f"Invalid tick: {tick}")


class UncodedInstructionError(Exception):
    def __init__(self, instruction: Instruction | None):
        super().__init__(f"Uncoded instruction: {instruction}")


class InvalidValueTypeFromMemoryError(Exception):
    def __init__(self, value: Any, index: int | None = None):
        super().__init__(f"Invalid value type from memory: {value} at {index}")


class UnexpectedNoneError(Exception):
    def __init__(self):
        super().__init__("Unexpected None")
