from __future__ import annotations

import re
import sys
from pathlib import Path

from computer_simulator.isa import Instruction
from computer_simulator.translator.expression_translator import Program, translate_program
from computer_simulator.translator.tokenizer import Token, tokenize


def run_translator(tokens: list[Token]) -> Program:
    program: Program = Program()
    translate_program(tokens, program)
    return program


def read_file(filename: str) -> str:
    return Path(filename).read_text(encoding="utf-8")


# find all expressions like (include "file") and replace them with the contents of the file
def preprocess(source: str) -> str:
    regex = re.compile(r'\(include\s+"(.+)"\)')
    match = regex.search(source)
    while match:
        file = match.group(1)
        source = source.replace(match.group(), read_file(file))
        match = regex.search(source)
    return source


def main(source: str, target: str) -> None:
    source_code: str = read_file(source)
    preprocessed_code: str = preprocess(source_code)
    tokenized_code: list[Token] = tokenize(preprocessed_code)
    program: Program = run_translator(tokenized_code)
    split_src_code = source_code.split("\n")
    print(
        f"source LoC: {len(split_src_code)} code instr: {len([x for x in program.memory if isinstance(x, Instruction)])}"
    )
    binary, log = program.to_machine_code()
    with open(target, "wb") as f:
        f.write(binary)
    with open(target + ".log", "w", encoding="utf-8") as f:
        f.write(log)


if __name__ == "__main__":
    assert len(sys.argv) == 3, f"Usage: python3 {Path(__file__).name} <source> <target>"
    main(sys.argv[1], sys.argv[2])
