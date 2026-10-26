"""The NetBBS door profile shipped with every release (#23).

SysOps import `profiles/netbbs.json` with NetBBS's [J] Import JSON to run a
release newer than the one NetBBS bundles, so it has to describe how this file
actually runs.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_the_profile_launches_this_door_natively_over_stdio():
    entry = json.loads((_ROOT / "profiles" / "netbbs.json").read_text(encoding="utf-8"))
    profile = entry["profile"]
    assert entry["name"] == "Retro Trivia"
    assert entry["args"] == ["{install_dir}/retro_trivia.py"]
    assert (profile["adapter"], profile["endpoint"], profile["encoding"]) == ("native", "stdio", "utf-8")
    assert profile["install_dir"].startswith("/")  # NetBBS requires an absolute path


def test_the_profile_never_sends_a_resize_signal():
    # The door has no SIGUSR1 handler, and the signal's default action ends it.
    source = (_ROOT / "retro_trivia.py").read_text(encoding="utf-8")
    assert "SIGUSR1" not in source
    profile = json.loads((_ROOT / "profiles" / "netbbs.json").read_text(encoding="utf-8"))["profile"]
    assert profile["resize_signal"] is False


def test_several_nodes_may_run_it_at_once():
    # Nothing is shared or saved between sessions, so concurrent play is safe.
    source = (_ROOT / "retro_trivia.py").read_text(encoding="utf-8")
    profile = json.loads((_ROOT / "profiles" / "netbbs.json").read_text(encoding="utf-8"))["profile"]
    assert profile["multinode_certified"] is True and profile["max_sessions"] > 1
    assert "sqlite3" not in source
