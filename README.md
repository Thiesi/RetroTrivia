# Retro Trivia

A quick, single-player trivia door game for BBSes. Pick a round of 5, 8, 12 or
20 questions from a bank of 251, answer each with one key, and see how you did.
Every launch is a fresh round; nothing is saved between calls.

Retro Trivia is **one Python file** (`retro_trivia.py`) with no dependencies
beyond the standard library. It needs Python 3.11 or newer and a terminal of at
least 40×12.

## Where it runs

- **NetBBS:** bundled. NetBBS ships a tagged release of this file
  (Thiesi/NetBBS#1226), so a NetBBS SysOp has nothing to install.
- **Other BBS software** (Synchronet, Mystic, ENiGMA½, …): planned. It needs
  DOOR32.SYS/DOOR.SYS support, CP437 output and DOOR32 socket mode. The plan is
  in Thiesi/NetBBS#1223, and the work is tracked in this repository's issues.
- **Standalone**, for trying it out: `python3 retro_trivia.py`.

## Development

```sh
python -m pip install pytest pytest-xdist
python -m pytest -n auto              # the suite
python tools/check_stdlib_only.py     # the door imports only the standard library
```

Retro Trivia was developed inside NetBBS until October 2026. Its history came
along, but issue numbers in older commits and comments refer to
[Thiesi/NetBBS](https://github.com/Thiesi/NetBBS) issues.

## Releases

Pushing a tag such as `v1.0.0` runs the suite and publishes that commit's
`retro_trivia.py`, byte-for-byte as stored in git, with a `SHA256SUMS` file.
NetBBS vendors these releases.

## License

BSD 2-Clause, see [LICENSE](LICENSE).
