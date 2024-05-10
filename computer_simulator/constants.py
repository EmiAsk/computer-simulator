from __future__ import annotations

# machine
WORD_SIZE: int = 32
WORD_MAX_VALUE: int = 2 ** (WORD_SIZE - 1) - 1
WORD_MIN_VALUE: int = -(2 ** (WORD_SIZE - 1))
REG_NUMBER = 2
DEFAULT_REGISTER = 0

# translator
EXPECTED_IDENTIFIER = "Expected identifier"
STATIC_MEMORY_SIZE = 64
STRING_ALLOC_SIZE = 8
SERVICE_VAR_ADDR = 1
