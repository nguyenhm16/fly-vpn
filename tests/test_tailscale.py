"""Tests for flyexit.tailscale.is_exit_node_active."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from flyexit import tailscale


def _status_result(peers: dict) -> MagicMock:
    return MagicMock(returncode=0, stdout=json.dumps({"Peer": peers}))


def test_is_exit_node_active_true_when_selected(monkeypatch):
    monkeypatch.setattr(
        tailscale.subprocess,
        "run",
        lambda *a, **k: _status_result(
            {"peer1": {"HostName": "fly-vpn-exit", "ExitNode": True}}
        ),
    )

    assert tailscale.is_exit_node_active() is True


def test_is_exit_node_active_false_when_online_but_not_selected(monkeypatch):
    """Online/visible in the tailnet is not the same as actually routed."""
    monkeypatch.setattr(
        tailscale.subprocess,
        "run",
        lambda *a, **k: _status_result(
            {"peer1": {"HostName": "fly-vpn-exit", "ExitNode": False}}
        ),
    )

    assert tailscale.is_exit_node_active() is False


def test_is_exit_node_active_false_when_absent(monkeypatch):
    monkeypatch.setattr(tailscale.subprocess, "run", lambda *a, **k: _status_result({}))

    assert tailscale.is_exit_node_active() is False


def test_is_exit_node_active_false_when_tailscale_missing(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(tailscale.subprocess, "run", _raise)

    assert tailscale.is_exit_node_active() is False
