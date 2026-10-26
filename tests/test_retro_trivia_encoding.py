"""CP437 artwork and the output boundary, independently of terminal colours."""

import ast
import io
import json
import os
import subprocess
import sys

import pytest

from .test_retro_trivia import _load, _PATH
from .test_retro_trivia_dropfiles import drop_file

rt = _load()


def test_all_authored_glyphs_have_deliberate_cp437_forms():
    tree = ast.parse(_PATH.read_text(encoding="utf-8"))
    docs = {id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            node.value.translate(rt._CP437_TRANSLATION).encode("cp437", "strict")


@pytest.mark.parametrize("width", [40, 80])
@pytest.mark.parametrize("screen", ["title", "length", "question", "right", "wrong",
                                   "farewell", "abandoned", "score", "splash", "finale"])
def test_every_screen_writes_strict_cp437_bytes(monkeypatch, width, screen):
    raw = io.BytesIO()
    terminal = io.TextIOWrapper(raw, encoding="cp437", newline="")
    monkeypatch.setattr(rt.sys, "stdout", terminal)
    monkeypatch.setattr(rt, "_OUTPUT_ENCODING", "cp437")
    monkeypatch.setattr(rt, "_OUTPUT_WIDTH", width)
    monkeypatch.setattr(rt, "read_key", lambda: "1" if screen == "length" else "A")
    convert = rt._cp437_text

    def strict(text):
        expected = text.translate(rt._CP437_TRANSLATION)
        expected.encode("cp437", "strict")  # No user-text fallback may hide missing artwork.
        assert convert(text) == expected
        return expected

    monkeypatch.setattr(rt, "_cp437_text", strict)
    p = rt.Palette(False, basic=True)
    info = {"handle": "Jäger", "node_name": "Test BBS"}
    w = width - 2
    actions = {
        "title": lambda: rt.draw_title(p, info, width=w),
        "length": lambda: rt.ask_round_length(p, width=w),
        "question": lambda: rt.ask_question(p, 1, 5, *rt.QUESTIONS[0][:2], width=w),
        "right": lambda: rt.draw_result(p, True, "A", "ANSI", width=w),
        "wrong": lambda: rt.draw_result(p, False, "A", "ANSI", width=w),
        "farewell": lambda: rt.draw_farewell(p, width=w),
        "abandoned": lambda: rt.draw_abandoned(p, 2, 3, width=w),
        "score": lambda: rt.draw_final_score(p, 3, 5, info, width=w),
        "splash": lambda: [rt.out(frame) for frame in rt.splash_frames(p, info, width, 24)],
        "finale": lambda: [rt.out(frame) for score in (5, 3, 1)
                           for frame in rt.finale_frames(p, info, score, 5, width, 24)],
    }
    actions[screen]()
    data = raw.getvalue()
    assert data and b"\x1b[" in data
    assert data.decode("cp437").encode("cp437") == data
    if screen in ("title", "score"):
        assert b"J\x84ger" in data
    assert b"\xe2\x95" not in data  # No UTF-8 box-drawing bytes.


def test_user_text_fallback_keeps_columns_and_terminal_controls():
    text = "\x1b[2J\x1b[H Jäger Łódź 界 🚀 e\u0301\r\n"
    mapped = rt._cp437_text(text)
    assert mapped.startswith("\x1b[2J\x1b[H Jäger") and mapped.endswith("\r\n")
    assert "?" not in mapped
    assert rt._visible_width(mapped) == rt._visible_width(text)
    mapped.encode("cp437", "strict")


@pytest.mark.parametrize("host", ["standalone", "classic", "malformed", "netbbs"])
@pytest.mark.parametrize("encoding", ["auto", "utf-8", "cp437"])
def test_command_line_encoding_selection(tmp_path, monkeypatch, host, encoding):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    args = [sys.executable, str(_PATH), "--encoding", encoding]
    if host in ("classic", "malformed"):
        args.append(drop_file(tmp_path, count=3 if host == "malformed" else None,
                              changes={1: "0", 2: "0"}))
    if host == "netbbs":
        path = tmp_path / "host.json"
        path.write_text(json.dumps({"handle": "Jäger"}), encoding="utf-8")
        monkeypatch.setenv("NETBBS_DOOR_INFO", str(path))
        args.append(drop_file(tmp_path))
    result = subprocess.run(args, input=b"Q", capture_output=True, timeout=30, env=dict(os.environ))
    assert result.returncode == 0, result.stderr
    expected = ("utf-8" if host == "netbbs" else
                ("cp437" if host in ("classic", "malformed") else "utf-8")
                if encoding == "auto" else encoding)
    # The round card's frame: CP437 has the glyph, so either encoding can draw it.
    assert "─".encode(expected) in result.stdout
    other = "utf-8" if expected == "cp437" else "cp437"
    assert "─".encode(other) not in result.stdout


# -- no-graphics callers (#16) ---------------------------------------------

@pytest.mark.parametrize("kind,line,value,depth", [
    ("DOOR32.SYS", 10, "0", "none"), ("DOOR32.SYS", 10, "1", "16"),
    ("DOOR.SYS", 20, "NG", "none"), ("DOOR.SYS", 20, "7e", "none"), ("DOOR.SYS", 20, "GR", "16"),
])
def test_a_no_graphics_emulation_selects_plain_output(tmp_path, kind, line, value, depth):
    assert rt._load_door_info(drop_file(tmp_path, kind, changes={line: value}))["color_depth"] == depth


@pytest.mark.parametrize("width", [40, 80])
@pytest.mark.parametrize("screen", ["title", "length", "question", "right", "wrong",
                                   "farewell", "abandoned", "score"])
@pytest.mark.parametrize("encoding", ["cp437", "utf-8"])
def test_every_screen_is_plain_ascii_for_a_no_graphics_caller(monkeypatch, width, screen, encoding):
    raw = io.BytesIO()
    terminal = io.TextIOWrapper(raw, encoding=encoding, newline="")
    monkeypatch.setattr(rt.sys, "stdout", terminal)
    monkeypatch.setattr(rt, "_OUTPUT_ENCODING", encoding)
    monkeypatch.setattr(rt, "_OUTPUT_WIDTH", width)
    monkeypatch.setattr(rt, "_PLAIN", True)
    monkeypatch.setattr(rt, "read_key", lambda: "1" if screen == "length" else "A")
    p = rt.Palette(False, basic=True)
    info = {"handle": "Jäger 界", "node_name": "Test BBS"}
    w = width - 2
    {
        "title": lambda: rt.draw_title(p, info, width=w),
        "length": lambda: rt.ask_round_length(p, width=w),
        "question": lambda: rt.ask_question(p, 1, 5, *rt.QUESTIONS[0][:2], width=w),
        "right": lambda: rt.draw_result(p, True, "A", "ANSI", width=w),
        "wrong": lambda: rt.draw_result(p, False, "A", "ANSI", width=w),
        "farewell": lambda: rt.draw_farewell(p, width=w),
        "abandoned": lambda: rt.draw_abandoned(p, 2, 3, width=w),
        "score": lambda: rt.draw_final_score(p, 3, 5, info, width=w),
    }[screen]()
    terminal.flush()
    data = raw.getvalue()
    assert data and b"\x1b" not in data
    assert all(32 <= byte < 127 or byte in b"\r\n" for byte in data), data
    if screen in ("title", "score"):
        assert b"Jager __" in data  # caller text folded to ASCII, its columns kept
    for row in data.decode("ascii").split("\r\n"):
        assert len(row) <= width


def test_a_no_graphics_caller_gets_no_splash_or_finale(monkeypatch):
    monkeypatch.delenv("DOOR_SPLASH", raising=False)
    monkeypatch.setattr(rt, "_PLAIN", True)

    class Poll:
        def waiting(self, timeout):
            return False

        def take(self, timeout):
            return False

    buffer = io.StringIO()
    monkeypatch.setattr(rt.sys, "stdout", buffer)
    assert not rt.play_splash(rt.Palette(False, basic=True), {}, 80, 24, poll=Poll())
    assert not rt.play_finale(rt.Palette(False, basic=True), {}, 5, 5, 80, 24, poll=Poll())
    assert buffer.getvalue() == ""


@pytest.mark.parametrize("kind,changes", [
    ("DOOR32.SYS", {1: "0", 2: "0", 10: "0"}), ("DOOR.SYS", {20: "NG"}), ("DOOR.SYS", {20: "7E"}),
])
def test_command_line_plays_a_plain_round(tmp_path, kind, changes):
    path = drop_file(tmp_path, kind, changes=changes)
    env = dict(os.environ)
    env.pop("DOOR_SPLASH", None)  # the splash and finale must stay off by themselves
    result = subprocess.run([sys.executable, str(_PATH), path], input=b"1AAAAAX",
                            capture_output=True, timeout=30, env=env)
    assert result.returncode == 0, result.stderr
    assert b"Final score:" in result.stdout
    assert b"\x1b" not in result.stdout
    assert all(32 <= byte < 127 or byte in b"\r\n" for byte in result.stdout)
