"""Keep local test scratch bounded (AGENTS.md, "Local disk hygiene").

In November 2026, scratch left by test runs on this development host grew
to several million files and took the host down. Every run wrote a new
folder and nothing ever removed one. Moving the scratch to the system temp
folder only moved the pile: that folder later passed half a million entries
and had to be cleared by hand.

Three checks run before any test:
- an explicit --basetemp inside the checkout must be `.test-tmp/pytest`,
  the one fixed name, so each run replaces the last;
- the checkout's ignored scratch (`.test-tmp`, `.pytest_cache`) must hold
  no more than SCRATCH_LIMIT files. Above that, run
  `python tools/clean_scratch.py` first;
- this project's entries in the system temp folder (`retro-trivia*`) must
  hold no more than SCRATCH_LIMIT files. Above that, run
  `python tools/clean_scratch.py --temp` first.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

SCRATCH_DIRS = (".test-tmp", ".pytest_cache")
LOCAL_BASETEMP = Path(".test-tmp") / "pytest"
DEFAULT_LIMIT = 50_000
# pytest-of-* is left out: pytest bounds it (see pyproject.toml), and other
# projects' runs share it.
TEMP_PATTERNS = ("retro-trivia*",)
LIMIT_VARIABLE = "RETROTRIVIA_SCRATCH_LIMIT"


def scratch_limit() -> int:
    return int(os.environ.get(LIMIT_VARIABLE, DEFAULT_LIMIT))


def count_files(root: Path, stop_after: int) -> int:
    """Files under root, counting at most stop_after + 1 so a huge tree stays cheap."""
    count, pending = 0, [root]
    while pending:
        try:
            entries = os.scandir(pending.pop())
        except OSError:
            continue
        with entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                        continue
                except OSError:
                    continue
                count += 1
                if count > stop_after:
                    return count
    return count


def basetemp_problem(basetemp: str | os.PathLike[str] | None, root: Path) -> str | None:
    if not basetemp:
        return None
    path, root = Path(basetemp).resolve(), root.resolve()
    if not path.is_relative_to(root) or path == (root / LOCAL_BASETEMP).resolve():
        return None
    return (f"--basetemp {path} is inside the checkout under a name that is never cleaned. "
            f"Leave out --basetemp (pytest then uses the system temp folder and keeps only failed "
            f"runs) or use --basetemp={LOCAL_BASETEMP.as_posix()}, which every run replaces.")


def scratch_problem(root: Path, limit: int | None = None) -> str | None:
    limit = scratch_limit() if limit is None else limit
    total = 0
    for name in SCRATCH_DIRS:
        if (root / name).is_dir():
            total += count_files(root / name, limit - total)
            if total > limit:
                return (f"This checkout holds more than {limit:,} scratch files in "
                        f"{' and '.join(SCRATCH_DIRS)}. Run `python tools/clean_scratch.py` "
                        f"(keep any evidence you need in docs/ or on the PR first). "
                        f"{LIMIT_VARIABLE} raises the limit for one run.")
    return None


def temp_folders(temp: Path | None = None) -> list[Path]:
    temp = Path(tempfile.gettempdir()) if temp is None else temp
    return sorted(path for pattern in TEMP_PATTERNS for path in temp.glob(pattern))


def temp_files(temp: Path | None = None, stop_after: int = 10**9) -> int:
    total = 0
    for path in temp_folders(temp):
        # A link counts as one entry: its target isn't this project's scratch.
        total += count_files(path, stop_after - total) if path.is_dir() and not path.is_symlink() else 1
        if total > stop_after:
            break
    return total


def temp_problem(temp: Path | None = None, limit: int | None = None) -> str | None:
    limit = scratch_limit() if limit is None else limit
    if temp_files(temp, limit) > limit:
        return (f"This project holds more than {limit:,} files in the system temp folder "
                f"({', '.join(TEMP_PATTERNS)}). The temp folder is not storage. Run "
                f"`python tools/clean_scratch.py --temp` (keep any evidence you need on the PR or "
                f"in docs/ first). That keeps entries written to in the last 24 hours; once no run "
                f"is active, `--temp --older-than 0` removes them too. "
                f"{LIMIT_VARIABLE} raises the limit for one run.")
    return None
