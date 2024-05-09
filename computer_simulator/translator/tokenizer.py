from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from computer_simulator.translator.errors import InvalidSymbolsError

IDENTIFIER_NON_ALPHA_CHARS = {"_"}


@dataclass
class Token:
    class Type(Enum):
        IF: int = auto()
        OPEN_BRACKET: int = auto()
        CLOSE_BRACKET: int = auto()
        BINOP: int = auto()
        BOOLEAN: int = auto()
        INT: int = auto()
        STRING: int = auto()
        SETQ: int = auto()
        IDENTIFIER: int = auto()
        DEFUN: int = auto()
        PRINT_CHAR: int = auto()
        PRINT_STRING: int = auto()
        PROGN: int = auto()
        READ_STRING: int = auto()
        WHILE: int = auto()
        READ_CHAR: int = auto()

    token_type: Type
    value: str


def process_whitespace(idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    while idx < len(chars) and chars[idx] in (" ", "\n", "\t"):
        idx += 1
    return idx


def process_brackets(tokens: list, idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    if chars[idx] == "(":
        tokens.append(Token(Token.Type.OPEN_BRACKET, chars[idx]))
        idx += 1
    elif chars[idx] == ")":
        tokens.append(Token(Token.Type.CLOSE_BRACKET, chars[idx]))
        idx += 1
    return idx


def process_binpos(tokens: list, idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    if chars[idx] in ("+", "-", "*", "/", "=", "<", ">", "%"):
        tokens.append(Token(Token.Type.BINOP, chars[idx]))
        idx += 1
    return idx


def process_number_literal(tokens: list, idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    start_idx = idx
    while idx < len(chars) and (chars[idx].isdigit() or start_idx == idx and chars[idx] == "-"):
        idx += 1
    if idx > start_idx:
        tokens.append(Token(Token.Type.INT, chars[start_idx:idx]))
    return idx


def char_allowed_in_identifier(c: str) -> bool:
    return c.isalpha() or c in IDENTIFIER_NON_ALPHA_CHARS


def process_identifier(tokens: list, idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    start_idx = idx
    while idx < len(chars) and char_allowed_in_identifier(chars[idx]):
        idx += 1
    if idx > start_idx:
        tokens.append(Token(Token.Type.IDENTIFIER, chars[start_idx:idx]))
    return idx


def process_string_literal(tokens: list, idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    if chars[idx] == '"':
        value = ""
        idx += 1
        while idx < len(chars) and chars[idx] != '"':
            value += chars[idx]
            idx += 1

        if idx >= len(chars):
            raise InvalidSymbolsError(got="string index out of range", expected="closing quote")

        tokens.append(Token(Token.Type.STRING, value))
        idx += 1
    return idx


def process_booleans(tokens: list, idx: int, chars: str) -> int:
    if idx >= len(chars):
        return idx
    if chars[idx] in ("T", "F"):
        tokens.append(Token(Token.Type.BOOLEAN, chars[idx]))
        idx += 1
    return idx


def process_keyword(tokens: list, idx: int, chars: str, token_type: Token.Type, keyword: str) -> int:
    if idx >= len(chars):
        return idx
    value = ""
    end_idx = idx
    while end_idx < len(chars) and (chars[end_idx].isalpha() or chars[end_idx] in IDENTIFIER_NON_ALPHA_CHARS):
        value += chars[end_idx]
        end_idx += 1
    if value == keyword:
        tokens.append(Token(token_type, keyword))
        return end_idx

    return idx


TOKEN_HANDLERS: list[Callable[[list[Token], int, str], int]] = [
    lambda tokens, idx, chars: process_whitespace(idx, chars),
    process_booleans,
    process_brackets,
    process_binpos,
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.IF, "if"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.SETQ, "setq"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.DEFUN, "defun"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.PRINT_CHAR, "print_char"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.PRINT_STRING, "print_string"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.PROGN, "progn"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.READ_STRING, "read_string"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.WHILE, "while"),
    lambda tokens, idx, chars: process_keyword(tokens, idx, chars, Token.Type.READ_CHAR, "read_char"),
    process_number_literal,
    process_string_literal,
    process_identifier,
]


def tokenize(program_chars: str) -> list[Token]:
    tokens: list[Token] = []
    idx: int = 0

    while idx < len(program_chars):
        start_idx = idx
        for handler in TOKEN_HANDLERS:
            idx = handler(tokens, idx, program_chars)
            if idx > start_idx:
                break
        if idx == start_idx:
            raise InvalidSymbolsError(got=program_chars[idx], expected="any known token")

    return tokens
