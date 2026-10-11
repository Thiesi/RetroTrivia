"""Classic host metadata, terminal-safe names, and NetBBS compatibility."""

import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

from .test_retro_trivia import _load, _PATH


rt = _load()
FIXTURES = Path(__file__).parent / "fixtures" / "dropfiles"


@pytest.fixture(autouse=True)
def no_host_environment(monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)


def drop_file(tmp_path, kind="DOOR32.SYS", *, changes=None, count=None,
              newline="\n", filename=None, encoding="utf-8"):
    lines = (FIXTURES / kind).read_text(encoding="utf-8").splitlines()
    for line, value in (changes or {}).items():
        lines[line - 1] = value
    if count is not None:
        lines = lines[:count]
    target = tmp_path / (filename or kind)
    target.write_bytes((newline.join(lines) + newline).encode(encoding))
    return str(target)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("filename", [None, "dOoR32.sYs", "caller.dat"])
def test_door32_golden_file(tmp_path, newline, filename):
    assert rt._load_door_info(drop_file(tmp_path, newline=newline, filename=filename)) == {
        "handle": "Starfox", "user_id": 77, "node_name": "Test BBS",
        "terminal_width": 80, "terminal_height": 24, "color_depth": "16",
        "drop_file_type": "DOOR32.SYS", "minutes_left": 25,
        "comm_type": 2, "comm_handle": 1234, "emulation": 1,
    }


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("count,handle", [(31, "Test Pilot"), (52, "Starfox")])
@pytest.mark.parametrize("filename", [None, "dOoR.sYs", "caller.dat"])
def test_door_sys_golden_file(tmp_path, newline, count, handle, filename):
    assert rt._load_door_info(drop_file(tmp_path, "DOOR.SYS", newline=newline,
                                      count=count, filename=filename)) == {
        "handle": handle, "user_id": 77, "node_name": "Local",
        "terminal_width": 80, "terminal_height": 30, "color_depth": "16",
        "drop_file_type": "DOOR.SYS", "minutes_left": 25,
        "comm_port": "COM1:", "emulation": "GR",
    }


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp437"])
@pytest.mark.parametrize("kind,line", [("DOOR32.SYS", 7), ("DOOR.SYS", 36)])
def test_alias_encoding_and_empty_alias_fallback(tmp_path, encoding, kind, line):
    assert rt._load_door_info(drop_file(tmp_path, kind, changes={line: "Jäger"},
                                       encoding=encoding))["handle"] == "Jäger"
    assert rt._load_door_info(drop_file(tmp_path, kind, changes={line: ""}))["handle"] == "Test Pilot"


@pytest.mark.parametrize("kind,count,changes", [
    ("DOOR32.SYS", 0, {}), ("DOOR32.SYS", 10, {}), ("DOOR.SYS", 30, {}),
    ("DOOR32.SYS", None, {1: "3"}), ("DOOR32.SYS", None, {2: "-1"}),
    ("DOOR32.SYS", None, {5: "0"}), ("DOOR32.SYS", None, {5: "-77"}),
    ("DOOR32.SYS", None, {5: "UNUSED_TEST_PASSWORD"}),
    ("DOOR32.SYS", None, {5: "9" * 5000}),
    ("DOOR32.SYS", None, {9: "-1"}), ("DOOR32.SYS", None, {10: "99"}),
    ("DOOR.SYS", None, {1: "junk"}), ("DOOR.SYS", None, {26: "0"}),
    ("DOOR.SYS", None, {21: "0"}), ("DOOR.SYS", None, {19: "oops"}),
    ("DOOR.SYS", None, {20: "bad"}),
])
def test_malformed_file_uses_complete_defaults_and_warns(tmp_path, capsys, kind, count, changes):
    info = rt._load_door_info(drop_file(tmp_path, kind, count=count, changes=changes))
    assert info == dict(rt._load_door_info(), color_depth="16")
    warning = capsys.readouterr().err
    assert "drop file ignored" in warning and "Guest defaults" in warning
    assert "UNUSED_TEST_PASSWORD" not in warning


def test_missing_or_unknown_file_warns(tmp_path, capsys):
    for path in (tmp_path / "absent", tmp_path / "random.txt"):
        if path.name == "random.txt":
            path.write_text("not a drop file", encoding="utf-8")
        assert rt._load_door_info(str(path)) == dict(rt._load_door_info(), color_depth="16")
        assert "drop file ignored" in capsys.readouterr().err


@pytest.mark.parametrize("data", [None, {}, {"user_id": 19, "handle": "NetPilot",
    "node_name": "My NetBBS", "terminal_width": 64, "terminal_height": 20,
    "color_depth": "truecolor"}, [], "broken"])
def test_netbbs_always_takes_precedence(tmp_path, monkeypatch, capsys, data):
    netbbs = tmp_path / "door_info.json"
    if data is not None:
        netbbs.write_text("invalid JSON" if data == "broken" else json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("NETBBS_DOOR_INFO", str(netbbs))
    info = rt._load_door_info(drop_file(tmp_path))
    expected = {"handle": "Guest", "user_id": 0, "terminal_width": 80,
                "terminal_height": 24, "color_depth": "256", "node_name": "NetBBS"}
    if isinstance(data, dict):
        expected.update(data)
    assert info == rt._load_door_info() == expected
    assert not capsys.readouterr().err


@pytest.mark.parametrize("escape", [
    "\x1b[31m", "\x1b[?25l", "\x1b]0;INJECTED\x07",
    "\x1b]0;INJECTED\x1b\\", "\x1bPINJECTED\x1b\\",
    "\x9b31m", "\x9d0;INJECTED\x9c", "\x00\x07\x08\x0b\x7f\u202e",
])
@pytest.mark.parametrize("kind,line", [("DOOR32.SYS", 7), ("DOOR32.SYS", 4),
                                       ("DOOR.SYS", 10), ("DOOR.SYS", 36)])
def test_foreign_names_are_safe_on_every_screen(tmp_path, capsys, escape, kind, line):
    changes = {line: "Safe" + escape + "Name"}
    if kind == "DOOR.SYS" and line == 10:
        changes[36] = ""
    info = rt._load_door_info(drop_file(tmp_path, kind, changes=changes))
    key = "node_name" if line == 4 else "handle"
    assert info[key] == "SafeName"
    palette = rt.Palette(False, basic=True)
    rt.draw_title(palette, info)
    rt.draw_final_score(palette, 3, 5, info=info)
    output = capsys.readouterr().out
    splash = rt._Splash(palette, info, 80, 24, random.Random(1))
    assert (splash.node if key == "node_name" else splash.handle) == "SafeName"
    assert output.count("SafeName") >= 2
    assert "INJECTED" not in output
    assert escape not in output


def test_control_only_names_fall_back_to_safe_defaults(tmp_path):
    info = rt._load_door_info(drop_file(tmp_path, changes={4: "\x1b[31m", 6: "\x07", 7: "\x00"}))
    assert info["handle"] == "Guest" and info["node_name"] == "Local"


def test_neutral_host_on_every_screen(capsys):
    info = rt._load_door_info()
    assert info["node_name"] == "Local"
    palette = rt.Palette(False)
    rt.draw_title(palette, {})
    rt.draw_final_score(palette, 3, 5)
    output = capsys.readouterr().out
    assert "NetBBS" not in output and "Local" in output
    assert rt._Splash(palette, {}, 80, 24, random.Random(1)).node == "Local"


def test_classic_splash_uses_only_basic_ansi_colors():
    frames = list(rt.splash_frames(rt.Palette(False, basic=True), {}, 80, 24))
    assert frames
    for frame in frames:
        assert "38;" not in frame and "48;" not in frame
        for sgr in re.findall(r"\x1b\[([0-9;]*)m", frame):
            assert all(int(code) in {0, 1, 2, *range(30, 38), *range(40, 48)}
                       for code in sgr.split(";") if code)


@pytest.mark.parametrize("kind", ["DOOR32.SYS", "DOOR.SYS"])
def test_command_line_plays_a_complete_round(tmp_path, kind):
    path = drop_file(tmp_path, kind, filename="caller metadata.dat",
                     changes={1: "0", 2: "0"} if kind == "DOOR32.SYS" else {})
    result = subprocess.run([sys.executable, str(_PATH), path], input=b"1AAAAAX",
                            capture_output=True, timeout=30, env=dict(os.environ))
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert b"Starfox" in result.stdout and b"Final score:" in result.stdout
    assert b"38;5;" not in result.stdout and b"38;2;" not in result.stdout


def test_malformed_command_line_file_still_launches(tmp_path):
    result = subprocess.run([sys.executable, str(_PATH), drop_file(tmp_path, count=3)],
                            input=b"Q", capture_output=True, timeout=30, env=dict(os.environ))
    assert result.returncode == 0, result.stderr
    assert b"drop file ignored" in result.stderr
    assert b"Guest" in result.stdout and b"Local" in result.stdout
