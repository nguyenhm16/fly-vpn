"""Tests for flyexit.headless (--start/--stop)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from flyexit import headless
from flyexit.session import (
    ConnectStatus,
    LaunchResult,
    LaunchStatus,
    PreflightResult,
    PreflightStatus,
)


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(
        headless.config,
        "load",
        lambda: {
            "app_name": "fly-vpn-node-abc123",
            "org": "personal",
            "region": "ams",
            "vm_memory": 512,
        },
    )


def test_run_start_no_auth_exits(monkeypatch):
    session = MagicMock(has_auth=False)
    monkeypatch.setattr(headless, "_build_session", lambda: session)

    with pytest.raises(SystemExit):
        headless.run_start()

    session.preflight.assert_not_called()


def test_run_start_preflight_failure_exits(monkeypatch):
    session = MagicMock(has_auth=True)
    session.preflight.return_value = PreflightResult(
        status=PreflightStatus.TAILSCALE_MISSING, error="Tailscale CLI not found."
    )
    monkeypatch.setattr(headless, "_build_session", lambda: session)

    with pytest.raises(SystemExit):
        headless.run_start()

    session.launch.assert_not_called()


def test_run_start_launch_failure_tears_down_and_exits(monkeypatch):
    session = MagicMock(has_auth=True)
    session.preflight.return_value = PreflightResult(
        status=PreflightStatus.OK, app_name="fly-vpn-node-abc123", username="me"
    )
    session.launch.return_value = LaunchResult(
        status=LaunchStatus.MACHINE_FAILED, error="boom"
    )
    monkeypatch.setattr(headless, "_build_session", lambda: session)

    with pytest.raises(SystemExit):
        headless.run_start()

    session.teardown.assert_called_once()


def test_run_start_happy_path_connects_without_exiting(monkeypatch):
    session = MagicMock(has_auth=True)
    session.preflight.return_value = PreflightResult(
        status=PreflightStatus.OK, app_name="fly-vpn-node-abc123", username="me"
    )
    session.launch.return_value = LaunchResult(status=LaunchStatus.OK)
    session.wait_and_connect.return_value = ConnectStatus.CONNECTED
    monkeypatch.setattr(headless, "_build_session", lambda: session)

    headless.run_start()  # should not raise/exit

    session.teardown.assert_not_called()
    args, kwargs = session.launch.call_args
    assert args == ("fly-vpn-node-abc123", "ams")
    assert kwargs["vm_memory"] == 512


def test_run_stop_nothing_running(monkeypatch):
    monkeypatch.setattr(headless, "app_exists", lambda _name: False)
    disconnect_mock = MagicMock()
    monkeypatch.setattr(headless, "disconnect_exit_node", disconnect_mock)
    build_mock = MagicMock()
    monkeypatch.setattr(headless, "_build_session", build_mock)

    headless.run_stop()

    disconnect_mock.assert_called_once()
    build_mock.assert_not_called()


def test_run_stop_destroys_running_app(monkeypatch):
    monkeypatch.setattr(headless, "app_exists", lambda _name: True)
    session = MagicMock(_client=None)
    session.teardown.return_value = ("fly-vpn-node-abc123", True)
    monkeypatch.setattr(headless, "_build_session", lambda: session)

    headless.run_stop()  # should not raise/exit

    session.attach.assert_called_once_with("fly-vpn-node-abc123")
    session.teardown.assert_called_once()


def test_run_stop_exits_on_teardown_failure(monkeypatch):
    monkeypatch.setattr(headless, "app_exists", lambda _name: True)
    session = MagicMock(_client=None)
    session.teardown.return_value = ("fly-vpn-node-abc123", False)
    monkeypatch.setattr(headless, "_build_session", lambda: session)

    with pytest.raises(SystemExit):
        headless.run_stop()
