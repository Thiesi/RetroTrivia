"""Standalone terminal ownership, raw keys, and restoration on exit."""

import io
import json
import os
import re
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from .test_retro_trivia import _load, _PATH
from .test_retro_trivia_dropfiles import drop_file

rt = _load()


@pytest.fixture(autouse=True)
def no_host(monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    monkeypatch.setattr(rt, "_CONSOLE_INPUT", None)


def test_standalone_defaults_use_terminal_dimensions(monkeypatch):
    monkeypatch.setattr(rt.shutil, "get_terminal_size", lambda **kwargs: os.terminal_size((61, 19)))
    info = rt._load_door_info()
    assert (info["terminal_width"], info["terminal_height"]) == (61, 19)


@pytest.mark.parametrize("host", ["netbbs", "classic", "missing"])
def test_bbs_dimensions_do_not_use_local_terminal(tmp_path, monkeypatch, host):
    def forbidden(**kwargs):
        pytest.fail("A BBS launch tried to measure the SysOp's terminal")

    monkeypatch.setattr(rt.shutil, "get_terminal_size", forbidden)
    if host == "netbbs":
        path = tmp_path / "info.json"
        path.write_text(json.dumps({"terminal_width": 51, "terminal_height": 22}), encoding="utf-8")
        monkeypatch.setenv("NETBBS_DOOR_INFO", str(path))
        info = rt._load_door_info()
        expected = (51, 22)
    elif host == "classic":
        info = rt._load_door_info(drop_file(tmp_path, "DOOR.SYS"))
        expected = (80, 30)
    else:
        info = rt._load_door_info(str(tmp_path / "missing"))
        expected = (80, 24)
    assert (info["terminal_width"], info["terminal_height"]) == expected


@pytest.mark.parametrize("host", ["netbbs", "classic", "pipe"])
def test_bbs_or_redirected_input_is_not_reconfigured(monkeypatch, host):
    monkeypatch.setattr(rt.sys, "stdin", io.StringIO())
    if host == "netbbs":
        monkeypatch.setenv("NETBBS_DOOR_INFO", "host.json")
    with rt._standalone_terminal("DOOR.SYS" if host == "classic" else None):
        assert rt._CONSOLE_INPUT is None


def console(monkeypatch, keys):
    queue = list(keys)
    fake = SimpleNamespace(getwch=lambda: queue.pop(0), kbhit=lambda: bool(queue))
    monkeypatch.setattr(rt, "os", SimpleNamespace(name="nt", environ=os.environ))
    monkeypatch.setattr(rt.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    return queue


def test_windows_console_reads_one_key_without_enter(monkeypatch):
    queue = console(monkeypatch, ["\xe0", "H", "A", "Q"])
    with rt._standalone_terminal(None):
        assert rt.read_key() == "A"  # The arrow key's H tail is not an answer.
        assert rt.read_key() == "Q"
    assert not queue and rt._CONSOLE_INPUT is None


def test_windows_console_splash_peeks_and_spends_whole_keys(monkeypatch):
    queue = console(monkeypatch, ["\x00", "K", "Q"])
    with rt._standalone_terminal(None):
        poll = rt._open_key_poll()
        assert poll.waiting(0)
        assert len(queue) == 3
        assert poll.take(0) and queue == ["Q"]
        assert rt.read_key() == "Q"
        assert not poll.take(0)


def test_windows_ctrl_c_restores_the_input_reader(monkeypatch):
    console(monkeypatch, ["\x03"])
    with pytest.raises(KeyboardInterrupt):
        with rt._standalone_terminal(None):
            rt.read_key()
    assert rt._CONSOLE_INPUT is None


@pytest.mark.skipif(os.name != "nt", reason="requires a real Windows console")
def test_real_windows_console_ctrl_c_exits_without_an_extra_key(tmp_path):
    report = tmp_path / "console-result.json"
    script = r'''
import ctypes, json, pathlib, runpy, sys, threading
assert sys.stdin.isatty(), "test requires console input"
# The test runner may inherit an ignore-Ctrl-C flag from its launcher.
# A regular interactive console has Ctrl-C delivery enabled.
assert ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
main = runpy.run_path(sys.argv[1])["main"]
def interrupt():
    ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0)
timer = threading.Timer(0.5, interrupt)
timer.start()
result = main()
timer.join()
pathlib.Path(sys.argv[2]).write_text(json.dumps({
    "status": result, "restored": main.__globals__["_CONSOLE_INPUT"] is None,
}))
'''
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0  # Exercise a real console without opening a visible window.
    env = dict(os.environ, DOOR_SPLASH="0")
    env.pop("NETBBS_DOOR_INFO", None)
    proc = subprocess.Popen([sys.executable, "-c", script, str(_PATH), str(report)],
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
                            startupinfo=startup, env=env)
    try:
        assert proc.wait(timeout=10) == 0
        assert json.loads(report.read_text()) == {"status": 130, "restored": True}
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


@pytest.mark.skipif(os.name != "posix", reason="requires a real POSIX PTY")
@pytest.mark.parametrize("exit_key,returncode", [(b"Q", 0), (b"\x03", 130)])
def test_real_tty_single_keys_size_and_restoration(exit_key, returncode):
    import fcntl
    import pty
    import select
    import struct
    import termios

    master, slave = pty.openpty()
    original = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 18, 60, 0, 0))
    env = dict(os.environ, DOOR_SPLASH="0")
    for key in ("NETBBS_DOOR_INFO", "COLUMNS", "LINES"):
        env.pop(key, None)
    # Give the subprocess a controlling terminal, so a typed Ctrl-C really
    # generates SIGINT rather than simulating it through a test-side signal.
    wrapper = ("import os,fcntl,termios,runpy,sys; os.setsid(); "
               "fcntl.ioctl(0,termios.TIOCSCTTY,0); sys.argv=sys.argv[1:]; "
               "runpy.run_path(sys.argv[0],run_name='__main__')")
    proc = subprocess.Popen([sys.executable, "-c", wrapper, str(_PATH)],
                            stdin=slave, stdout=slave, stderr=subprocess.PIPE, env=env)
    output = bytearray()

    def read_until(marker):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            plain = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", output)
            if marker in plain:
                return plain.decode("utf-8")
            if select.select([master], [], [], 0.1)[0]:
                output.extend(os.read(master, 65536))
        pytest.fail(f"TTY prompt {marker!r} never appeared: {output[-1000:]!r}")

    try:
        screen = read_until(b"How many questions?")
        assert max(rt._visible_width(row) for row in screen.splitlines()) <= 60
        current = termios.tcgetattr(slave)
        assert not current[3] & (termios.ICANON | termios.ECHO)
        if exit_key == b"Q":
            os.write(master, b"1")  # No Enter: this must immediately start a question.
            read_until(b"Your answer")
            os.write(master, b"\x1b[A\x1b[B\x1b[C\x1b[D\x1bOA\x1b[1;5DQ")
            screen = read_until(b"Press any key to leave")
            assert "Correct!" not in screen and "Not quite." not in screen
            os.write(master, b"X")
        else:
            os.write(master, exit_key)
        _, stderr = proc.communicate(timeout=10)
        assert proc.returncode == returncode, stderr
        assert not stderr
        assert termios.tcgetattr(slave) == original
        if exit_key == b"\x03":
            while select.select([master], [], [], 0)[0]:
                output.extend(os.read(master, 65536))
            plain = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", output)
            assert plain.endswith(b"\r\n")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=5)
        os.close(master)
        os.close(slave)
