"""Fixtures shared by the Retro Trivia suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_door_splash(monkeypatch):
    """A door launched by a test opens straight on its first screen.

    A finished launch splash waits for a key. The splash's own tests take this
    back off (`monkeypatch.delenv`)."""
    monkeypatch.setenv("DOOR_SPLASH", "0")
    yield
