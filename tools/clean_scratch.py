"""Remove this checkout's local scratch, or report scratch across checkouts.

    python tools/clean_scratch.py            # clean the checkout this script is in
    python tools/clean_scratch.py --report   # file counts for the checkout, worktrees and temp folder
    python tools/clean_scratch.py --temp     # remove this project's stale entries in the temp folder
    python tools/clean_scratch.py --temp --older-than 0   # also recent ones; first check no run is active

Cleaning deletes only ignored, reproducible scratch: `.test-tmp`,
`.pytest_cache`, `__pycache__`, `build` and `*.egg-info` (never `.venv`,
never tracked files). Keep any evidence you need in docs/ or on the PR first.
`--temp` deletes only top-level `retro-trivia*` entries in the system temp
folder with nothing written for 24 hours, so a run still in progress is left
alone. `--older-than HOURS` changes the 24. It never touches anything else
there. The report never deletes anything; it flags trees over the limit and
worktrees whose branch is already on origin/main, so they can be removed with
`git worktree remove`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.scratch_guard import DEFAULT_LIMIT, SCRATCH_DIRS, count_files, temp_files, temp_folders  # noqa: E402

SKIP = {".git", ".venv", ".worktrees", "node_modules"}
ROOT_ONLY = {"build"}


def scratch_paths(root: Path) -> list[Path]:
    found = [root / name for name in (*SCRATCH_DIRS, *ROOT_ONLY) if (root / name).exists()]
    for top, dirs, _ in os.walk(root):
        at_root = Path(top) == root
        dirs[:] = [d for d in dirs if d not in SKIP and not (at_root and d in (*SCRATCH_DIRS, *ROOT_ONLY))]
        for d in list(dirs):
            if d == "__pycache__" or d.endswith(".egg-info"):
                found.append(Path(top) / d)
                dirs.remove(d)
    return found


def remove(path: Path) -> list[str]:
    failed: list[str] = []

    def retry(function, name, _error):
        try:
            os.chmod(name, stat.S_IWRITE)
            function(name)
        except OSError:
            failed.append(name)

    if path.is_symlink():
        # Remove the link only: chmod and rmtree would act on, or refuse, its target.
        try:
            path.unlink()
        except OSError:
            failed.append(str(path))
    elif path.is_dir():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=retry)
        else:
            shutil.rmtree(path, onerror=retry)
    else:
        retry(os.remove, str(path), None)
    return failed


def clean(root: Path) -> int:
    failed: list[str] = []
    for path in scratch_paths(root):
        failed += remove(path)
    failed = sorted(set(failed))
    left =sum(count_files(root / name, 10**9) for name in SCRATCH_DIRS if (root / name).is_dir())
    print(f"{root}: scratch removed; {left} files left, {len(failed)} paths could not be deleted.")
    if failed:
        print("Paths Windows refused (often folders left with a private ACL, for example by a"
              " OneDrive move); an administrator can take ownership and remove them:")
        for name in failed[:20]:
            print(f"  {name}")
    return 1 if failed else 0


def newest_write(path: Path) -> float:
    newest = path.lstat().st_mtime
    if path.is_dir() and not path.is_symlink():
        for top, dirs, files in os.walk(path):
            for name in dirs + files:
                try:
                    newest = max(newest, os.lstat(os.path.join(top, name)).st_mtime)
                except OSError:
                    continue
    return newest


def clean_temp(temp: Path | None = None, hours: float = 24, now: float | None = None) -> int:
    now = time.time() if now is None else now
    removed, kept, failed = 0, 0, []
    for path in temp_folders(temp):
        if now - newest_write(path) < hours * 3600:
            kept += 1
            continue
        refused = remove(path)
        failed += refused
        removed += not refused
    print(f"Temp folder: {removed} stale entries removed, {kept} written to in the last {hours:g} h kept, "
          f"{len(failed)} paths could not be deleted.")
    for name in sorted(set(failed))[:20]:
        print(f"  {name}")
    return 1 if failed else 0


def count_tree(tree: Path) -> int:
    """Files in a checkout, leaving out .git, .venv and nested worktrees."""
    total = 0
    for entry in os.scandir(tree):
        if entry.name in SKIP:
            continue
        total += count_files(Path(entry.path), 10**9) if entry.is_dir(follow_symlinks=False) else 1
    return total


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True).stdout.strip()


def report(root: Path, limit: int) -> int:
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    registered = {Path(line.split(" ", 1)[1]).resolve()
                  for line in git(common, "worktree", "list", "--porcelain").splitlines()
                  if line.startswith("worktree ")}
    # A worktree created outside .worktrees/ counts too.
    found = {p.resolve() for p in (common / ".worktrees").glob("*") if p.is_dir()} | registered
    trees = [common] + sorted(found - {common.resolve()})
    flagged = 0
    for tree in trees:
        total = count_tree(tree)
        notes = []
        if total > limit:
            notes.append(f"OVER {limit:,}")
        if tree != common and tree.resolve() not in registered:
            notes.append("not a registered worktree")
        elif tree != common and git(tree, "rev-parse", "HEAD") and \
                subprocess.run(["git", "-C", str(tree), "merge-base", "--is-ancestor", "HEAD", "origin/main"]).returncode == 0 \
                and not git(tree, "status", "--porcelain"):
            notes.append("no commits of its own: remove it if its PR has merged and no session is using it")
        flagged += any(note.startswith("OVER") for note in notes)
        print(f"{total:>9,}  {tree.name if tree != common else '(main checkout)'}  {'; '.join(notes)}")
    in_temp = temp_files()
    flagged += in_temp > limit
    over = f"OVER {limit:,}: run clean_scratch.py --temp" if in_temp > limit else ""
    print(f"{in_temp:>9,}  (system temp folder, {Path(tempfile.gettempdir())})  {over}")
    return 1 if flagged else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", action="store_true", help="report every worktree; delete nothing")
    parser.add_argument("--temp", action="store_true", help="remove this project's stale entries in the temp folder")
    parser.add_argument("--older-than", type=float, default=24, metavar="HOURS",
                        help="with --temp: keep entries written to more recently than this (default 24)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="files per tree before it is flagged")
    args = parser.parse_args(argv)
    if args.temp:
        return clean_temp(hours=args.older_than)
    return report(ROOT, args.limit) if args.report else clean(ROOT)


if __name__ == "__main__":
    sys.exit(main())
