"""Regression tests: attach()ing to a session must not arm implicit cleanup.

A front-end that merely *detects* an already-running session (browser TUI
opened via --web/--daemon while `fly-vpn --start` is running, or a second
terminal) must not destroy it just because that front-end's own process
exits. Only launch()ing a session (this instance actually created it) or
an explicit teardown() (Stop button / `--stop`) may destroy it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from flyexit import fly_api
from flyexit import session as session_module
from flyexit.session import LaunchStatus, VPNSession


def _session() -> VPNSession:
    return VPNSession(ts_auth_key="tskey-auth-test")


def test_attach_does_not_own_the_session():
    s = _session()
    s.attach("fly-vpn-node-test")

    assert s.is_active
    assert s._owns_app is False


def test_emergency_cleanup_noop_when_not_owned(monkeypatch):
    s = _session()
    s.attach("fly-vpn-node-test")

    disconnect_mock = MagicMock()
    cleanup_mock = MagicMock()
    monkeypatch.setattr(session_module, "disconnect_exit_node", disconnect_mock)
    monkeypatch.setattr(session_module, "cleanup_app_sync", cleanup_mock)

    s.emergency_cleanup()

    disconnect_mock.assert_not_called()
    cleanup_mock.assert_not_called()
    # State is left untouched — this instance never owned it, so it makes
    # no claim about whether the session is still running.
    assert s.app_name == "fly-vpn-node-test"


def test_emergency_cleanup_destroys_when_owned(monkeypatch):
    s = _session()
    s.app_name = "fly-vpn-node-test"
    s._owns_app = True

    disconnect_mock = MagicMock()
    cleanup_mock = MagicMock()
    monkeypatch.setattr(session_module, "disconnect_exit_node", disconnect_mock)
    monkeypatch.setattr(session_module, "cleanup_app_sync", cleanup_mock)

    s.emergency_cleanup()

    disconnect_mock.assert_called_once()
    cleanup_mock.assert_called_once_with("fly-vpn-node-test")
    assert s.app_name is None


def test_teardown_destroys_attached_but_unowned_session(monkeypatch):
    """Explicit Stop must work regardless of ownership."""
    s = _session()
    s.attach("fly-vpn-node-test")

    monkeypatch.setattr(session_module, "disconnect_exit_node", MagicMock())
    destroy_mock = MagicMock(return_value=True)
    monkeypatch.setattr(session_module, "destroy_app", destroy_mock)

    app_name, ok = s.teardown()

    assert (app_name, ok) == ("fly-vpn-node-test", True)
    destroy_mock.assert_called_once_with("fly-vpn-node-test")
    assert s.app_name is None
    assert s._owns_app is False


def test_launch_marks_ownership_even_on_early_failure(monkeypatch):
    """Ownership is claimed as soon as launch() is attempted, regardless of
    outcome — once we've tried to create resources, we're responsible for
    them."""
    s = _session()
    monkeypatch.setattr(fly_api, "get_client", lambda: None)

    result = s.launch("fly-vpn-node-test", "ams")

    assert result.status is LaunchStatus.ERROR
    assert s._owns_app is True
