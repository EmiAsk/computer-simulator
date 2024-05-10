from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, cast

from computer_simulator.constants import DEFAULT_REGISTER, REG_NUMBER, WORD_MAX_VALUE, WORD_MIN_VALUE
from computer_simulator.isa import Arg, ArgType, Instruction, Opcode
from computer_simulator.machine.errors import (
    InvalidArgTypeError,
    InvalidTickError,
    InvalidValueTypeFromMemoryError,
    UncodedInstructionError,
    UnexpectedNoneError,
    UnknownSignalError,
    UnknownStageError,
)


@dataclass(frozen=True)
class Port:
    value: int


STDIN: Port = Port(0)
STDOUT: Port = Port(1)


class IpSelSignal(Enum):
    INC = 0
    DR = 1


class SpSelSignal(Enum):
    INC = 0
    DEC = 1


class AddrSelSignal(Enum):
    AC = 0
    SP = 1
    IP = 2
    DR = 3


class AcSelSignal(Enum):
    IN = 0
    ALU = 1
    DR = 2
    IP = 3


class DrSelSignal(Enum):
    MEMORY = 1
    ALU = 2


class AluOp(Enum):
    ADD = 0
    SUB = 1
    EQ = 2
    GT = 3
    LT = 4
    MOD = 5
    DIV = 6
    MULT = 7


class AluLeft(Enum):
    AC = 0
    IP = 1
    SP = 2
    SRC1 = 3
    IMM1 = 4


class AluRight(Enum):
    ZERO = 0
    DR = 1
    SRC2 = 2
    IMM2 = 3


@dataclass
class SrcSelSignal:
    value: int


@dataclass
class DestSelSignal:
    value: int


class DestValSelSignal(Enum):
    IN = 0
    ALU = 1
    DR = 2
    MEMORY = 3


ALU_OP_HANDLERS: dict[AluOp, Callable[[int, int], int]] = {
    AluOp.ADD: lambda left, right: left + right,
    AluOp.SUB: lambda left, right: left - right,
    AluOp.EQ: lambda left, right: 1 if left == right else 0,
    AluOp.GT: lambda left, right: 1 if left > right else 0,
    AluOp.LT: lambda left, right: 1 if left < right else 0,
    AluOp.MOD: lambda left, right: left % right,
    AluOp.DIV: lambda left, right: left // right,
    AluOp.MULT: lambda left, right: left * right,
}


class Alu:
    def __init__(self) -> None:
        self.flag_z: int = 1

    def perform(self, op: AluOp, left: int, right: int) -> int:
        handler = ALU_OP_HANDLERS[op]
        value = handler(left, right)
        value = self.handle_overflow(value)
        self.set_flags(value)
        return value

    def set_flags(self, value) -> None:
        self.flag_z = int(value == 0)

    @staticmethod
    def handle_overflow(value: int) -> int:
        if value >= WORD_MAX_VALUE:
            return value - WORD_MAX_VALUE
        if value <= WORD_MIN_VALUE:
            return value + WORD_MAX_VALUE
        return value


class IO:
    def __init__(self, ports: dict[Port, list[int]]):
        self.ports: dict[Port, list[int]] = ports

    def read(self, port: Port):
        if not self.ports[port]:
            logging.debug("IN: %s", 0)
            return 0
        value = self.ports[port].pop(0)
        logging.debug('IN: %s - "%s"', value, chr(value))
        return value

    def write(self, port: Port, value: int):
        self.ports[port].append(value)


class DataPath:
    def __init__(self, memory: list[Instruction | int], io: IO) -> None:
        self.memory: list[Instruction | int] = memory
        self.alu: Alu = Alu()
        self.ip: int = 0  # instruction pointer
        self.dr: int = 0  # data register
        self.sp: int = len(self.memory)  # stack pointer
        self.ar: int = 0  # address register
        self.ac: int = 0  # accumulator
        self.regs: list[int] = [0] * REG_NUMBER
        self.io = io

    def reg_read(self, sel_src_1: SrcSelSignal, sel_src_2: SrcSelSignal) -> tuple[int, int]:
        return (
            self.regs[sel_src_1.value] if sel_src_1.value < len(self.regs) else None,
            self.regs[sel_src_2.value] if sel_src_2.value < len(self.regs) else None,
        )

    def reg_write(
        self,
        sel_dest: DestSelSignal,
        sel_dest_val: DestValSelSignal,
        alu_res: int | None = None,
        memory: int | None = None,
        port: int | None = None,
    ) -> None:
        signal_to_value = {
            DestValSelSignal.DR: self.dr,
            DestValSelSignal.ALU: alu_res,
            DestValSelSignal.IN: port,
            DestValSelSignal.MEMORY: memory,
        }
        if sel_dest_val not in signal_to_value:
            raise UnknownSignalError(sel_dest)
        value = signal_to_value[sel_dest_val]
        if value is None:
            raise UnexpectedNoneError()
        self.regs[sel_dest.value] = value

    def _get_reg_by_alu_left(self, alu_left: AluLeft, src_1: int | None = None, imm_1: int | None = None) -> int:
        if alu_left == AluLeft.IP:
            return self.ip
        if alu_left == AluLeft.SP:
            return self.sp
        if alu_left == AluLeft.IMM1:
            if imm_1 is None:
                raise UnexpectedNoneError()
            return imm_1
        if alu_left == AluLeft.SRC1:
            if src_1 is None:
                raise UnexpectedNoneError()
            return src_1
        raise UnknownSignalError(alu_left)

    def _get_reg_by_alu_right(self, alu_right: AluRight, src_2: int | None = None, imm_2: int | None = None) -> int:
        if alu_right == AluRight.ZERO:
            return 0
        if alu_right == AluRight.DR:
            return self.dr
        if alu_right == AluRight.IMM2:
            if imm_2 is None:
                raise UnexpectedNoneError()
            return imm_2
        if alu_right == AluRight.SRC2:
            if src_2 is None:
                raise UnexpectedNoneError()
            return src_2
        raise UnknownSignalError(alu_right)

    def signal_alu_perform(
        self,
        alu_op: AluOp,
        alu_left: AluLeft,
        alu_right: AluRight,
        src_1: int | None = None,
        src_2: int | None = None,
        imm_1: int | None = None,
        imm_2: int | None = None,
    ) -> int:
        left = self._get_reg_by_alu_left(alu_left, src_1, imm_1)
        right = self._get_reg_by_alu_right(alu_right, src_2, imm_2)
        return self.alu.perform(alu_op, left, right)

    def latch_ip(self, signal: IpSelSignal) -> None:
        if signal == IpSelSignal.INC:
            self.ip += 1
        elif signal == IpSelSignal.DR:
            self.ip = self.dr
        else:
            raise UnknownSignalError(signal)

    def latch_sp(self, signal: SpSelSignal) -> None:
        if signal == SpSelSignal.INC:
            self.sp += 1
        elif signal == SpSelSignal.DEC:
            self.sp -= 1
        else:
            raise UnknownSignalError(signal)

    def latch_dr(self, signal: DrSelSignal, alu_res: int | None = None, mem_value: int | None = None):
        if signal == DrSelSignal.MEMORY:
            if mem_value is None:
                raise UnexpectedNoneError()
            self.dr = cast(int, mem_value)
        elif signal == DrSelSignal.ALU:
            if alu_res is None:
                raise UnexpectedNoneError()
            self.dr = cast(int, alu_res)
        else:
            raise UnknownSignalError(signal)

    def _get_reg_by_addr_sel_signal(self, addr_sel_signal: AddrSelSignal) -> int:
        if addr_sel_signal == AddrSelSignal.SP:
            return self.sp
        if addr_sel_signal == AddrSelSignal.IP:
            return self.ip
        if addr_sel_signal == AddrSelSignal.DR:
            return self.dr

        raise UnknownSignalError(addr_sel_signal)

    def wr(self, addr_sel_signal: AddrSelSignal, src_1: int) -> None:
        self.memory[self._get_reg_by_addr_sel_signal(addr_sel_signal)] = src_1

    def oe(self, addr_sel_signal: AddrSelSignal) -> Instruction | int:
        return self.memory[self._get_reg_by_addr_sel_signal(addr_sel_signal)]


class Stage(Enum):
    INSTRUCTION_FETCH = 0
    ADDRESS_FETCH = 1
    OPERAND_FETCH = 2
    EXECUTE = 3


NO_FETCH_OPERAND = [
    Opcode.JMP,
    Opcode.JZ,
    Opcode.JNZ,
    Opcode.ST,
    Opcode.PUSH,
    Opcode.POP,
    Opcode.CALL,
]


class ControlUnit:
    def __init__(self, data_path: DataPath) -> None:
        self.data_path: DataPath = data_path
        self.stage: Stage = Stage.INSTRUCTION_FETCH  # stage counter
        self.tc: int = 0  # tick counter
        self.decoded_instruction: Instruction | None = None
        self.halted: bool = False

        # not a part of the control unit, but useful model information
        self.executed_instruction_n: int = 0
        self.tick_n: int = 0

    def latch_tc_inc(self) -> None:
        self.tc += 1

    def latch_tc_zero(self) -> None:
        self.tc = 0

    def tick(self) -> None:
        self.tick_n += 1
        handle_tick(self)

    def __repr__(self):
        stack = []
        for i in range(0, len(self.data_path.memory)):
            if self.data_path.sp + i < len(self.data_path.memory):
                stack.append(self.data_path.memory[self.data_path.sp + i])
            else:
                break

        return (
            f"TICK: {self.tick_n}, IP: {self.data_path.ip}, DR: {self.data_path.dr}, "
            f"Z: {self.data_path.alu.flag_z}, INSTR: {self.decoded_instruction}, SP: {self.data_path.sp}, "
            f"Stack: {stack}, REGS: {self.data_path.regs}"
        )


def _need_address_fetch(instruction: Instruction) -> bool:
    return instruction.opcode in (Opcode.LD, Opcode.ST) and instruction.args[-1].arg_type in (
        ArgType.STACK_OFFSET,
        ArgType.INDIRECT,
        ArgType.REGISTER,
    )


NO_FETCH_OPERAND_INSTR = [
    Opcode.JMP,
    Opcode.JZ,
    Opcode.JNZ,
    Opcode.ST,
    Opcode.PUSH,
    Opcode.POP,
    Opcode.CALL,
]


def _need_operand_fetch(instruction: Instruction) -> bool:
    return instruction.opcode == Opcode.LD and instruction.args[-1].arg_type != ArgType.IMMEDIATE


def find_next_stage_from_instruction_fetch(control_unit, decoded_instruction):
    if _need_address_fetch(decoded_instruction):
        control_unit.stage = Stage.ADDRESS_FETCH
    elif _need_operand_fetch(decoded_instruction):
        control_unit.stage = Stage.OPERAND_FETCH
    else:
        control_unit.stage = Stage.EXECUTE


def handle_instruction_fetch_tick(control_unit: ControlUnit):
    if control_unit.tc == 0:
        control_unit.executed_instruction_n += 1
        result = control_unit.data_path.oe(AddrSelSignal.IP)

        if not isinstance(result, Instruction):
            raise InvalidValueTypeFromMemoryError(result)
        control_unit.decoded_instruction = cast(Instruction, result)

        if not isinstance(control_unit.decoded_instruction, Instruction):
            raise InvalidValueTypeFromMemoryError(control_unit.decoded_instruction)
        decoded_instruction: Instruction = cast(Instruction, control_unit.decoded_instruction)

        if decoded_instruction.args and len(decoded_instruction.args) not in (0, 3):
            arg: Arg = cast(Arg, decoded_instruction.args[-1])
            control_unit.data_path.latch_dr(DrSelSignal.MEMORY, mem_value=arg.value)

        control_unit.data_path.latch_ip(IpSelSignal.INC)
        control_unit.latch_tc_zero()
        find_next_stage_from_instruction_fetch(control_unit, decoded_instruction)
    else:
        raise InvalidTickError(control_unit.tc)


def find_next_stage_after_address_fetch(control_unit, decoded_instruction):
    if _need_operand_fetch(decoded_instruction):
        control_unit.stage = Stage.OPERAND_FETCH
    else:
        control_unit.stage = Stage.EXECUTE


def handle_address_fetch_tick(control_unit: ControlUnit):
    data_path = control_unit.data_path
    instruction = control_unit.decoded_instruction

    if instruction is None:
        raise UncodedInstructionError(instruction)
    decoded_instruction: Instruction = cast(Instruction, instruction)

    if not decoded_instruction.args:
        raise UncodedInstructionError(instruction)
    arg: Arg = cast(Arg, decoded_instruction.args[-1])

    if arg.arg_type == ArgType.STACK_OFFSET:
        alu_res = data_path.signal_alu_perform(AluOp.ADD, AluLeft.SP, AluRight.DR)
        data_path.latch_dr(DrSelSignal.ALU, alu_res=alu_res)

        find_next_stage_after_address_fetch(control_unit, decoded_instruction)
    elif arg.arg_type == ArgType.INDIRECT:
        value = data_path.oe(AddrSelSignal.DR)
        if not isinstance(value, int):
            raise InvalidValueTypeFromMemoryError(value)

        data_path.latch_dr(DrSelSignal.MEMORY, mem_value=cast(int, value))

        find_next_stage_after_address_fetch(control_unit, decoded_instruction)
    elif arg.arg_type == ArgType.REGISTER:
        src_1, _ = data_path.reg_read(SrcSelSignal(arg.value), SrcSelSignal(arg.value))
        alu_res = data_path.signal_alu_perform(AluOp.ADD, AluLeft.SRC1, AluRight.ZERO, src_1=src_1)
        data_path.latch_dr(DrSelSignal.ALU, alu_res=alu_res)

        find_next_stage_after_address_fetch(control_unit, decoded_instruction)
    else:
        raise InvalidArgTypeError(arg.arg_type)


def handle_operand_fetch_tick(control_unit: ControlUnit):
    value = control_unit.data_path.oe(AddrSelSignal.DR)
    if not isinstance(value, int):
        raise InvalidValueTypeFromMemoryError(value)

    control_unit.data_path.latch_dr(DrSelSignal.MEMORY, mem_value=cast(int, value))

    control_unit.stage = Stage.EXECUTE


def command_handle_execute_ld(control_unit: ControlUnit):
    instruction = control_unit.decoded_instruction
    control_unit.data_path.reg_write(DestSelSignal(instruction.args[0].value), DestValSelSignal.DR)
    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_st(control_unit: ControlUnit):
    reg_number = control_unit.decoded_instruction.args[0].value
    src_1, _ = control_unit.data_path.reg_read(SrcSelSignal(reg_number), SrcSelSignal(reg_number))

    control_unit.data_path.wr(AddrSelSignal.DR, src_1)
    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_binop(control_unit: ControlUnit, op: AluOp):
    instruction = control_unit.decoded_instruction
    if control_unit.tc == 0:
        _, arg_1, arg_2 = instruction.args

        src_1, src_2 = control_unit.data_path.reg_read(SrcSelSignal(arg_1.value), SrcSelSignal(arg_2.value))
        imm_1, imm_2 = arg_1.value, arg_2.value

        if arg_1.arg_type == ArgType.IMMEDIATE:
            alu_left = AluLeft.IMM1
        else:
            alu_left = AluLeft.SRC1
        if arg_2.arg_type == ArgType.IMMEDIATE:
            alu_right = AluRight.IMM2
        else:
            alu_right = AluRight.SRC2

        alu_res = control_unit.data_path.signal_alu_perform(op, alu_left, alu_right, src_1, src_2, imm_1, imm_2)
        control_unit.data_path.latch_dr(DrSelSignal.ALU, alu_res=alu_res)
        control_unit.latch_tc_inc()
    elif control_unit.tc == 1:
        control_unit.data_path.reg_write(DestSelSignal(instruction.args[0].value), DestValSelSignal.DR)

        control_unit.latch_tc_zero()
        control_unit.stage = Stage.INSTRUCTION_FETCH
    else:
        raise InvalidTickError(control_unit.tc)


def command_handle_execute_jz(control_unit: ControlUnit):
    if control_unit.data_path.alu.flag_z:
        control_unit.data_path.latch_ip(IpSelSignal.DR)

    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_jnz(control_unit: ControlUnit):
    if not control_unit.data_path.alu.flag_z:
        control_unit.data_path.latch_ip(IpSelSignal.DR)

    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_jmp(control_unit: ControlUnit):
    control_unit.data_path.latch_ip(IpSelSignal.DR)

    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_push(control_unit: ControlUnit):
    instruction = control_unit.decoded_instruction
    if control_unit.tc == 0:
        control_unit.data_path.latch_sp(SpSelSignal.DEC)

        control_unit.latch_tc_inc()
    elif control_unit.tc == 1:
        sel_src_1 = SrcSelSignal(instruction.args[0].value)
        src_1, _ = control_unit.data_path.reg_read(sel_src_1, sel_src_1)
        control_unit.data_path.wr(AddrSelSignal.SP, src_1)

        control_unit.latch_tc_zero()
        control_unit.stage = Stage.INSTRUCTION_FETCH
    else:
        raise InvalidTickError(control_unit.tc)


def command_handle_execute_pop(control_unit: ControlUnit):
    control_unit.data_path.latch_sp(SpSelSignal.INC)
    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_in(control_unit: ControlUnit):
    instruction = control_unit.decoded_instruction
    arg_1, arg_2 = instruction.args

    value = control_unit.data_path.io.read(Port(arg_2.value))

    control_unit.data_path.reg_write(DestSelSignal(arg_1.value), DestValSelSignal.IN, port=value)

    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_out(control_unit: ControlUnit):
    instruction = control_unit.decoded_instruction
    arg_1, arg_2 = instruction.args
    sel_src_1 = SrcSelSignal(arg_1.value)
    src_1, _ = control_unit.data_path.reg_read(sel_src_1, sel_src_1)

    control_unit.data_path.io.write(Port(arg_2.value), src_1)

    control_unit.stage = Stage.INSTRUCTION_FETCH


def command_handle_execute_call(control_unit: ControlUnit):
    if control_unit.tc == 0:
        alu_res = control_unit.data_path.signal_alu_perform(AluOp.ADD, AluLeft.IP, AluRight.IMM2, imm_2=0)
        control_unit.data_path.reg_write(DestSelSignal(DEFAULT_REGISTER), DestValSelSignal.ALU, alu_res)
        control_unit.data_path.latch_sp(SpSelSignal.DEC)

        control_unit.latch_tc_inc()
    elif control_unit.tc == 1:
        src_1, _ = control_unit.data_path.reg_read(SrcSelSignal(DEFAULT_REGISTER), SrcSelSignal(DEFAULT_REGISTER))
        control_unit.data_path.wr(AddrSelSignal.SP, src_1)
        control_unit.data_path.latch_ip(IpSelSignal.DR)

        control_unit.latch_tc_zero()
        control_unit.stage = Stage.INSTRUCTION_FETCH
    else:
        raise InvalidTickError(control_unit.tc)


def command_handle_execute_ret(control_unit: ControlUnit):
    if control_unit.tc == 0:
        ret_addr = control_unit.data_path.oe(AddrSelSignal.SP)
        if not isinstance(ret_addr, int):
            raise InvalidValueTypeFromMemoryError(ret_addr)

        control_unit.data_path.latch_dr(DrSelSignal.MEMORY, mem_value=cast(int, ret_addr))

        control_unit.latch_tc_inc()
    elif control_unit.tc == 1:
        control_unit.data_path.latch_ip(IpSelSignal.DR)
        control_unit.data_path.latch_sp(SpSelSignal.INC)

        control_unit.latch_tc_zero()
        control_unit.stage = Stage.INSTRUCTION_FETCH
    else:
        raise InvalidTickError(control_unit.tc)


def command_handle_execute_hlt(control_unit: ControlUnit):
    control_unit.halted = True
    control_unit.stage = Stage.INSTRUCTION_FETCH


EXECUTE_HANDLERS: dict[Opcode, Callable[[ControlUnit], None]] = {
    Opcode.LD: command_handle_execute_ld,
    Opcode.ST: command_handle_execute_st,
    Opcode.ADD: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.ADD),
    Opcode.SUB: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.SUB),
    Opcode.MUL: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.MULT),
    Opcode.DIV: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.DIV),
    Opcode.MOD: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.MOD),
    Opcode.EQ: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.EQ),
    Opcode.LT: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.LT),
    Opcode.GT: lambda control_unit: command_handle_execute_binop(control_unit, AluOp.GT),
    Opcode.JZ: command_handle_execute_jz,
    Opcode.JNZ: command_handle_execute_jnz,
    Opcode.JMP: command_handle_execute_jmp,
    Opcode.PUSH: command_handle_execute_push,
    Opcode.POP: command_handle_execute_pop,
    Opcode.IN: command_handle_execute_in,
    Opcode.OUT: command_handle_execute_out,
    Opcode.CALL: command_handle_execute_call,
    Opcode.RET: command_handle_execute_ret,
    Opcode.HLT: command_handle_execute_hlt,
}


def handle_execute_tick(control_unit: ControlUnit):
    if control_unit.decoded_instruction is None:
        raise UncodedInstructionError(control_unit.decoded_instruction)

    handler: Callable[[ControlUnit], None] = EXECUTE_HANDLERS[
        cast(Instruction, control_unit.decoded_instruction).opcode
    ]
    handler(control_unit)


def handle_tick(control_unit: ControlUnit):
    if control_unit.stage == Stage.INSTRUCTION_FETCH:
        handle_instruction_fetch_tick(control_unit)
    elif control_unit.stage == Stage.ADDRESS_FETCH:
        handle_address_fetch_tick(control_unit)
    elif control_unit.stage == Stage.OPERAND_FETCH:
        handle_operand_fetch_tick(control_unit)
    elif control_unit.stage == Stage.EXECUTE:
        handle_execute_tick(control_unit)
    else:
        raise UnknownStageError(control_unit.stage)


def describe_hardwire_state(control_unit: ControlUnit, data_path: DataPath):
    stack = []
    for i in range(0, len(data_path.memory)):
        if data_path.sp + i < len(data_path.memory):
            stack.append(f"{data_path.memory[data_path.sp + i]}")
        else:
            break

    return (
        f"TICK: {control_unit.tick_n}, IP: {data_path.ip}, DR: {data_path.dr}, "
        f"Z: {data_path.alu.flag_z}, INSTR: {control_unit.decoded_instruction}, SP: {data_path.sp}, "
        f"Stack: {stack}, REGS: {data_path.regs}"
    )
