"""The disk-hygiene guards (tests/scratch_guard.py, tools/clean_scratch.py)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from tests import scratch_guard as guard
from tools import clean_scratch


def fill(folder: Path, count: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (folder / f"f{i}").write_text("x")


def test_basetemp_outside_the_checkout_or_the_fixed_name_is_allowed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    assert guard.basetemp_problem(None, root) is None
    assert guard.basetemp_problem(tmp_path / "elsewhere", root) is None
    assert guard.basetemp_problem(root / ".test-tmp" / "pytest", root) is None


def test_any_other_basetemp_inside_the_checkout_is_refused(tmp_path):
    problem = guard.basetemp_problem(tmp_path / ".test-tmp" / "run-42", tmp_path)
    assert problem and ".test-tmp/pytest" in problem


def test_checkout_scratch_over_the_limit_is_refused(tmp_path):
    fill(tmp_path / ".test-tmp" / "a", 3)
    fill(tmp_path / ".pytest_cache", 2)
    assert guard.scratch_problem(tmp_path, limit=5) is None
    fill(tmp_path / ".pytest_cache" / "more", 1)
    assert "clean_scratch.py" in guard.scratch_problem(tmp_path, limit=5)


def test_only_this_projects_temp_entries_count(tmp_path):
    fill(tmp_path / "retro-trivia" / "captures", 4)
    fill(tmp_path / "pytest-of-someone", 10)
    fill(tmp_path / "other-project", 10)
    assert guard.temp_files(tmp_path) == 4
    assert guard.temp_problem(tmp_path, limit=4) is None
    assert "--temp" in guard.temp_problem(tmp_path, limit=3)


def test_cleaning_removes_scratch_but_not_tracked_files_or_venv(tmp_path, monkeypatch):
    fill(tmp_path / ".test-tmp" / "pytest", 2)
    fill(tmp_path / "tests" / "__pycache__", 2)
    fill(tmp_path / "build", 1)
    fill(tmp_path / ".venv" / "lib" / "__pycache__", 1)
    (tmp_path / "retro_trivia.py").write_text("print()")
    assert clean_scratch.clean(tmp_path) == 0
    assert not (tmp_path / ".test-tmp").exists()
    assert not (tmp_path / "tests" / "__pycache__").exists()
    assert not (tmp_path / "build").exists()
    assert (tmp_path / ".venv" / "lib" / "__pycache__" / "f0").exists()
    assert (tmp_path / "retro_trivia.py").exists()


def test_temp_cleaning_keeps_recent_entries(tmp_path):
    stale, fresh = tmp_path / "retro-trivia-old", tmp_path / "retro-trivia-new"
    fill(stale, 1)
    fill(fresh, 1)
    fill(tmp_path / "unrelated", 1)
    old = time.time() - 48 * 3600
    for path in (stale / "f0", stale):
        os.utime(path, (old, old))
    assert clean_scratch.clean_temp(tmp_path, hours=24) == 0
    assert not stale.exists()
    assert fresh.exists() and (tmp_path / "unrelated").exists()
