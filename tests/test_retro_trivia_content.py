"""The question bank and the text wrapper, checked against the shipped file.

Both lived in NetBBS's `tests/test_doors_runtime.py` until the move
(Thiesi/NetBBS#1223); NetBBS keeps its tests of how it launches the door.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "retro_trivia.py"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def test_the_question_bank_is_large_and_well_formed():
    module = _load("retro_trivia_questions_under_test")
    prompts = [question for question, _choices, _correct in module.QUESTIONS]
    assert len(prompts) >= 100
    assert len(prompts) == len(set(prompts))
    assert all(len(choices) == 4 for _question, choices, _correct in module.QUESTIONS)
    assert all(len(set(choices)) == 4 for _question, choices, _correct in module.QUESTIONS)
    assert all(0 <= correct < 4 for _question, _choices, correct in module.QUESTIONS)


def test_the_wrapper_normalizes_tabs_and_keeps_indentation_with_content():
    module = _load("retro_trivia_wrap_under_test")
    tabbed = module._wrap_output("1234\t56789", 10)
    indented = module._wrap_output("  0123456789", 5)
    combining = module._wrap_output("aaa\u0301b", 3)
    boxed = module._wrap_output("\x1b[35m│\x1b[37m" + ("word " * 12) + "\x1b[35m│\x1b[0m", 20)

    assert tabbed == "1234 56789"
    assert indented.split("\r\n") == ["  012", "34567", "89"]
    assert combining.split("\r\n") == ["aaa\u0301", "b"]
    boxed_rows = boxed.split("\r\n")
    assert len(boxed_rows) > 1
    assert all(row.startswith("\x1b[35m│\x1b[37m") for row in boxed_rows)
