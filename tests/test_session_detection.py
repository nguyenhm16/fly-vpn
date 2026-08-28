"""Regression tests for detecting a session started from elsewhere.

Without this, opening a fresh front-end (browser TUI via --web/--daemon,
or a second terminal) while a session created by `fly-vpn --start` (or
another front-end) is still running would show a blank/idle UI — and
clicking Launch would destroy-and-recreate the real running app, since
ensure_app_exists() unconditionally wipes any existing app with the same
name.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest
from textual.widgets import Button

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch):
    """FlyVPNApp with all external I/O neutralised except fly_ops.app_exists."""
    from flyexit import config as cfg_module

    monkeypatch.setattr(cfg_module, "load", lambda: {"region": "ams"})
    monkeypatch.setattr(cfg_module, "save", lambda _: None)
    monkeypatch.setenv("TAILSCALE_AUTHKEY", "")
    monkeypatch.setenv("TAILSCALE_API_KEY", "")

    from flyexit.app import FlyVPNApp

    return FlyVPNApp()


async def _poll(condition: Callable[[], bool], *, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if condition():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"condition never became True within {timeout}s")


# ---------------------------------------------------------------------------


async def test_detects_already_running_session(app, monkeypatch):
    from flyexit import fly_ops

    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: True)

    async with app.run_test():
        await _poll(lambda: app.query_one("#btn-launch", Button).disabled)

        assert app._session.is_active
        assert app.query_one("#btn-stop", Button).disabled is False


async def test_no_false_positive_when_nothing_running(app, monkeypatch):
    from flyexit import fly_ops

    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: False)

    async with app.run_test():
        await _poll(lambda: app._session_detection_ran, timeout=2.0)

        assert app._session.app_name is None
        assert not app._session.is_active
        assert app.query_one("#btn-stop", Button).disabled is True


async def test_launch_blocked_when_session_already_detected(app, monkeypatch):
    """Clicking Launch on a detected session must not call preflight —
    that would trigger ensure_app_exists() and destroy the real app."""
    from flyexit import fly_ops

    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: True)
    app._session.preflight = lambda *a, **k: pytest.fail(
        "preflight() must not run against an already-detected session"
    )

    with contextlib.suppress(Exception):
        async with app.run_test():
            await _poll(lambda: app._session.app_name is not None)
            app._do_launch()
            await asyncio.sleep(0.2)  # let a wrongly-started worker misfire
