import contextlib
import io
import logging
import os
import tempfile

import pytest
from computer_simulator.constants import WORD_SIZE
from computer_simulator.machine import machine
from computer_simulator.translator import translator


@pytest.mark.golden_test("../golden/*.yml")
def test_whole_by_golden(golden, caplog):
    caplog.set_level(logging.DEBUG)

    with tempfile.TemporaryDirectory() as tmpdirname:
        source = os.path.join(tmpdirname, "source")
        input_stream = os.path.join(tmpdirname, "input")
        target = os.path.join(tmpdirname, "target")

        with open(source, "w", encoding="utf-8") as file:
            file.write(golden["source"])
        with open(input_stream, "w", encoding="utf-8") as file:
            file.write(golden["input"])

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            translator.main(source, target)
            print("============================================================")
            machine.main(target, input_stream)

        words = []
        with open(target, mode="rb") as file:
            data = file.read().hex()
            for i in range(0, len(data), WORD_SIZE // 4):
                words.append(data[i : i + WORD_SIZE // 4])
        code = "\n".join(words)

        with open(f"{target}.log", encoding="utf-8") as file:
            disasm = file.read()

        assert code == golden.out["code"]
        assert stdout.getvalue() == golden.out["output"]
        assert caplog.text == golden.out["log"]
        assert disasm == golden.out["disasm"]
