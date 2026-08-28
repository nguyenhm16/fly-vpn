"""Regression tests for detecting a session started from elsewhere.

Without this, opening a fresh front-end (browser TUI via --web/--daemon,
or a second terminal) while a session created by `fly-vpn --start` (or
another front-end) is still running would show a blank/idle UI — and
clicking Launch would destroy-and-recreate the real running app, since
ensure_app_exists() unconditionally wipes any existing app with the same
name. Launch also starts disabled until the initial check completes, so
a click can't land in the race window before detection resolves.
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
    """FlyVPNApp with all external I/O neutralised except fly_ops.app_exists.

    Isolates from this machine's *real* ~/.fly_vpn.db keystore (which may
    hold genuine credentials from actual use) — otherwise has_auth's value
    would depend on whoever's machine runs the suite, since keystore wins
    over the env vars set below.
    """
    from flyexit import config as cfg_module
    from flyexit import keystore as keystore_module

    monkeypatch.setattr(cfg_module, "load", lambda: {"region": "ams"})
    monkeypatch.setattr(cfg_module, "save", lambda _: None)
    monkeypatch.setattr(keystore_module, "get", lambda _key, default="": default)
    monkeypatch.setenv("TAILSCALE_AUTHKEY", "tskey-auth-test")
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


async def test_launch_disabled_while_initial_check_in_flight(app, monkeypatch):
    """Closes the race: Launch must stay disabled until the startup check
    resolves — otherwise a click could land concurrently with a session
    started elsewhere, corrupting both (this is what produced the
    'HTTP error contacting Fly.io API' failure in practice)."""
    import threading

    from flyexit import fly_ops

    release = threading.Event()

    def slow_app_exists(_name: str) -> bool:
        release.wait(timeout=5)
        return False

    monkeypatch.setattr(fly_ops, "app_exists", slow_app_exists)

    async with app.run_test():
        await asyncio.sleep(0.1)  # give the worker a chance to start
        assert app.query_one("#btn-launch", Button).disabled is True

        release.set()
        await _poll(lambda: not app.query_one("#btn-launch", Button).disabled)


async def test_detects_already_running_session(app, monkeypatch):
    from flyexit import fly_ops

    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: True)

    async with app.run_test():
        await _poll(lambda: not app.query_one("#btn-stop", Button).disabled)

        assert app._session.is_active
        assert app._session._owns_app is False
        assert app.query_one("#btn-launch", Button).disabled is True


async def test_no_false_positive_when_nothing_running(app, monkeypatch):
    from flyexit import fly_ops

    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: False)

    async with app.run_test():
        await _poll(lambda: not app.query_one("#btn-launch", Button).disabled)

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


async def test_refresh_button_detects_newly_started_session(app, monkeypatch):
    from flyexit import fly_ops

    running = {"value": False}
    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: running["value"])

    async with app.run_test() as pilot:
        await _poll(lambda: not app.query_one("#btn-launch", Button).disabled)

        running["value"] = True
        await pilot.click("#btn-refresh")
        await _poll(lambda: not app.query_one("#btn-stop", Button).disabled)

        assert app._session.is_active


async def test_refresh_button_detects_session_ended_elsewhere(app, monkeypatch):
    from flyexit import fly_ops

    running = {"value": True}
    monkeypatch.setattr(fly_ops, "app_exists", lambda _name: running["value"])

    async with app.run_test() as pilot:
        await _poll(lambda: not app.query_one("#btn-stop", Button).disabled)
        assert app._session.is_active

        running["value"] = False
        await pilot.click("#btn-refresh")
        await _poll(lambda: not app.query_one("#btn-launch", Button).disabled)

        assert not app._session.is_active
        assert app.query_one("#btn-stop", Button).disabled is True
