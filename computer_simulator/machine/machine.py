from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from computer_simulator.constants import WORD_SIZE
from computer_simulator.isa import Arg, ArgType, Instruction, Opcode
from computer_simulator.machine.errors import UnknownOpcodeError
from computer_simulator.machine.hardwire import IO, STDIN, STDOUT, ControlUnit, DataPath

MEMORY_SIZE: int = 2048


@dataclass
class BinaryProgram:
    memory: list[Instruction | int]


def read_file(file_path: str) -> str:
    with open(file_path, encoding="utf-8") as file:
        return file.read()


def read_json_file(file_path: str) -> dict:
    return json.loads(read_file(file_path))


def read_input(file_path: str) -> list[int]:
    with open(file_path, encoding="utf-8") as file:
        file_str = file.read()
        return [ord(c) for c in file_str]


def bytes_to_instruction(b: bytes) -> Instruction:
    bin_word = bin(int(b.hex(), 16))[2:].rjust(WORD_SIZE, "0")
    bin_opcode = bin_word[:5]
    opcode = Opcode(int(bin_opcode, 2))
    args: list[Arg] = []
    if opcode in (Opcode.HLT, Opcode.POP, Opcode.RET):
        args = []
    elif opcode in (Opcode.LD, Opcode.ST):
        arg_1_bin = bin_word[5 : 5 + 3]
        mode_bin = bin_word[5 + 3 : 5 + 3 + 3]
        arg_2_bin = bin_word[5 + 3 + 3 :]
        args += [Arg(int(arg_1_bin, 2), ArgType.REGISTER), Arg(int(arg_2_bin, 2), ArgType(int(mode_bin, 2)))]
    elif opcode in (Opcode.JMP, Opcode.CALL, Opcode.PUSH):
        arg_1_bin = bin_word[5:]
        args += [
            Arg(int(arg_1_bin, 2), ArgType.ADDRESS),
        ]
    elif opcode in (Opcode.JNZ, Opcode.JZ):
        arg_1_bin = bin_word[5 : 5 + 3]
        arg_2_bin = bin_word[5 + 3 :]
        args += [Arg(int(arg_1_bin, 2), ArgType.REGISTER), Arg(int(arg_2_bin, 2), ArgType.ADDRESS)]
    elif opcode in (Opcode.IN, Opcode.OUT):
        arg_1_bin = bin_word[5 : 5 + 3]
        arg_2_bin = bin_word[5 + 3 :]
        args += [Arg(int(arg_1_bin, 2), ArgType.REGISTER), Arg(int(arg_2_bin, 2), ArgType.PORT)]
    elif opcode in (Opcode.ADD, Opcode.SUB, Opcode.LT, Opcode.GT, Opcode.EQ, Opcode.MOD, Opcode.DIV, Opcode.MUL):
        arg_1_bin = bin_word[5 : 5 + 3]
        mode_2_bin = bin_word[5 + 3 : 5 + 3 + 1]
        arg_2_bin = bin_word[5 + 3 + 1 : 5 + 3 + 1 + 11]
        mode_3_bin = bin_word[5 + 3 + 1 + 11 : 5 + 3 + 1 + 11 + 1]
        arg_3_bin = bin_word[5 + 3 + 1 + 11 + 1 :]
        args += [
            Arg(int(arg_1_bin, 2), ArgType.REGISTER),
            Arg(int(arg_2_bin, 2), ArgType(int(mode_2_bin, 2))),
            Arg(int(arg_3_bin, 2), ArgType(int(mode_3_bin, 2))),
        ]
    else:
        raise UnknownOpcodeError(opcode)
    return Instruction(opcode, args if args else None)


def read_program(exe: str) -> BinaryProgram:
    memory: list[Instruction | int] = [0 for _ in range(MEMORY_SIZE)]
    with open(exe, mode="rb") as file:
        words = []
        while True:
            word = file.read(4)
            if len(word) != 4:
                break
            words.append(word)
    first_word = words[0]
    jmp_instr = bytes_to_instruction(first_word)
    jmp_index = jmp_instr.args[0].value
    for k, word in enumerate(words):
        if 1 <= k < jmp_index:
            memory[k] = int(word.hex(), 16)
            continue
        memory[k] = bytes_to_instruction(word)
    return BinaryProgram(memory)


def simulation(program: BinaryProgram, limit: int, program_input: list[int]) -> tuple[list[int], int, int]:
    """
    Simulate program execution
    :return: output, instructions_n, ticks_n
    """
    io: IO = IO({STDIN: program_input, STDOUT: []})
    data_path: DataPath = DataPath(program.memory, io)
    control_unit: ControlUnit = ControlUnit(data_path)

    logging.debug("%s", control_unit)
    while not control_unit.halted and control_unit.tick_n < limit:
        control_unit.tick()
        logging.debug("%s", control_unit)

    return data_path.io.ports[STDOUT], control_unit.executed_instruction_n, control_unit.tick_n


def main(code: str, input_file: str) -> None:
    program: BinaryProgram = read_program(code)
    program_input: list[int] = read_input(input_file)

    result = simulation(program, limit=1_000_000, program_input=program_input)

    print("".join([chr(c) for c in result[0]]))
    print(f"instructions_n: {result[1]} ticks: {result[2]}")


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) >= 3, f"Usage: python3 {Path(__file__).name} <code> <input>"
    main(sys.argv[1], sys.argv[2])
