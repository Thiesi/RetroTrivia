"""Fixtures shared by the Retro Trivia suite."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def pytest_configure(config: pytest.Config) -> None:
    """Refuse runs that would grow unbounded local scratch (tests/scratch_guard.py)."""
    from tests.scratch_guard import basetemp_problem, scratch_problem, temp_problem
    problem = basetemp_problem(config.option.basetemp, REPO_ROOT) or scratch_problem(REPO_ROOT) or temp_problem()
    if problem:
        raise pytest.UsageError(problem)
    if config.option.basetemp:
        Path(config.option.basetemp).resolve().parent.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def _no_door_splash(monkeypatch):
    """A door launched by a test opens straight on its first screen.

    A finished launch splash waits for a key. The splash's own tests take this
    back off (`monkeypatch.delenv`)."""
    monkeypatch.setenv("DOOR_SPLASH", "0")
    yield
