"""Inherited socket launches and telnet framing, with no live BBS needed."""

import os
import re
import socket
import subprocess
import sys
import time

import pytest

from .test_retro_trivia import _load, _PATH
from .test_retro_trivia_dropfiles import drop_file

rt = _load()


@pytest.fixture
def wire(monkeypatch):
    local, peer = socket.socketpair()
    transport = rt._SocketTransport(local.detach())
    peer.settimeout(2)
    monkeypatch.setattr(rt, "_SOCKET_TRANSPORT", transport)
    monkeypatch.setattr(rt, "_PUSHBACK", [])
    yield transport, peer
    transport.close()
    peer.close()


@pytest.mark.parametrize("control", [b"\xff\xfbA", b"\xff\xfcB", b"\xff\xfdC",
                                     b"\xff\xfeD", b"\xff\xf1",
                                     b"\xff\xfa\x18ABCD\xff\xffQ\xff\xf0"])
def test_telnet_traffic_cannot_answer_questions(wire, control):
    transport, peer = wire
    peer.sendall(b"A" + control + b"B")
    assert rt.read_key() == "A"
    assert rt.read_key() == "B"
    assert transport(0) is None


def test_fragmented_commands_survive_poll_timeouts(wire):
    transport, peer = wire
    for fragment in (b"\xff", b"\xfb", b"A", b"\xff\xfa\x18ABC\xff"):
        peer.sendall(fragment)
        assert transport(0.01) is None
    peer.sendall(b"\xf0D\xff\xff")
    assert transport(0.1) == b"D"
    assert transport(0.1) == b"\xff"


@pytest.mark.parametrize("ending", [b"\r\x00", b"\r\n", b"\r\xff\xfbA\x00", b"\r\xff\xfdB\n"])
def test_telnet_enter_is_one_key(wire, ending):
    transport, peer = wire
    peer.sendall(ending + b"A")
    assert rt.read_key() == "\r"
    assert rt.read_key() == "A"
    assert transport(0) is None


def test_output_escapes_iac_after_cp437_encoding(wire, monkeypatch):
    _, peer = wire
    monkeypatch.setattr(rt, "_OUTPUT_ENCODING", "cp437")
    rt.out("\x1b[31mJäger\u00a0!\r\n")  # CP437 NBSP is 0xff.
    assert peer.recv(100) == b"\x1b[31mJ\x84ger\xff\xff!\r\n"


def test_splash_poll_filters_negotiation_and_preserves_typed_key(wire):
    transport, peer = wire
    poll = rt._open_key_poll()
    assert isinstance(poll, rt._SocketPoll)
    peer.sendall(b"\xff\xfbA")
    assert not poll.waiting(0.05)
    peer.sendall(b"Q")
    assert poll.waiting(0.1)
    assert rt.read_key() == "Q"
    assert transport(0) is None


def test_closed_connection_reports_carrier_loss(wire):
    transport, peer = wire
    peer.close()
    with pytest.raises(rt._CarrierLost):
        rt.read_key()
    with pytest.raises(rt._CarrierLost):
        rt.out("screen")
    assert transport.lost


def test_partial_writes_keep_nonblocking_host_mode(wire):
    transport, peer = wire
    real = transport.socket
    real.setblocking(False)

    class PartialSocket:
        def __getattr__(self, name):
            return getattr(real, name)

        def send(self, data):
            return real.send(data[:2])

    transport.socket = PartialSocket()
    transport.write(b"A\xffB\xffC")
    received = bytearray()
    while len(received) < 7:
        received.extend(peer.recv(7 - len(received)))
    assert received == b"A\xff\xffB\xff\xffC"
    assert not real.getblocking()


class SocketDoor:
    def __init__(self, directory, *, splash=False):
        self.host, self.peer = socket.socketpair()
        self.host.set_inheritable(True)
        path = drop_file(directory, changes={2: str(self.host.fileno())})
        self.output = bytearray()
        self.peer.settimeout(0.1)
        env = dict(os.environ, DOOR_SPLASH="1" if splash else "0")
        env.pop("NETBBS_DOOR_INFO", None)
        inheritance = {"close_fds": False} if os.name == "nt" else {"pass_fds": (self.host.fileno(),)}
        self.proc = subprocess.Popen([sys.executable, str(_PATH), path], stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **inheritance)

    def read_until(self, marker=None):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if marker is not None and (marker in self.output or
                                       marker in re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", self.output)):
                return
            try:
                data = self.peer.recv(8192)
            except TimeoutError:
                if self.proc.poll() is not None:
                    break
                continue
            if not data:
                break
            self.output.extend(data)
        if marker is not None:
            pytest.fail(f"Missing socket prompt {marker!r}: {self.output[-1000:]!r}")

    def finish(self, *, drain=True):
        if drain:
            self.read_until()
        stdout, stderr = self.proc.communicate(timeout=15)
        assert self.proc.returncode == 0, stderr
        assert not stdout, "socket game output leaked to stdout"
        assert not stderr

    def close(self):
        self.host.close()
        self.peer.close()
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.communicate(timeout=5)


@pytest.fixture
def socket_door(tmp_path):
    sessions = []

    def launch(**kwargs):
        door = SocketDoor(tmp_path, **kwargs)
        sessions.append(door)
        return door

    yield launch
    for door in sessions:
        door.close()


def test_inherited_socket_plays_a_round_and_returns_to_host(socket_door):
    door = socket_door()
    door.peer.sendall(b"1A\xff\xfbBAAAA\r\x00")
    door.finish()
    assert b"Final score:" in door.output and b"Starfox" in door.output
    door.host.sendall(b"Back at the BBS")
    assert door.peer.recv(100) == b"Back at the BBS"


@pytest.mark.parametrize("stage", ["title", "question", "splash"])
def test_carrier_drop_ends_the_process_cleanly(socket_door, stage):
    door = socket_door(splash=stage == "splash")
    if stage == "question":
        door.peer.sendall(b"1")
        door.read_until(b"Your answer")
    elif stage == "title":
        door.read_until(b"How many questions?")
    else:
        door.read_until(b"\x1b[?25l")
    door.peer.close()
    door.finish(drain=False)


def test_invalid_handle_reports_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    path = drop_file(tmp_path, changes={2: "123456789"})
    result = subprocess.run([sys.executable, str(_PATH), path], capture_output=True,
                            input=b"Q", timeout=15, env=dict(os.environ))
    assert result.returncode == 1
    assert b"cannot open inherited DOOR32 socket" in result.stderr
    assert b"Traceback" not in result.stderr and not result.stdout
