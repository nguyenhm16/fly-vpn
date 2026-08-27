"""Tests for flyexit.webserver.run_web."""

from __future__ import annotations

import shlex
import sys
from unittest.mock import MagicMock

from flyexit import config as config_module
from flyexit import webserver


def test_run_web_uses_explicit_port(monkeypatch):
    server_cls = MagicMock()
    monkeypatch.setattr(webserver, "Server", server_cls)
    monkeypatch.setattr(config_module, "load", lambda: {"web_port": 8000})

    webserver.run_web(port=9999)

    _, kwargs = server_cls.call_args
    assert kwargs["port"] == 9999
    server_cls.return_value.serve.assert_called_once_with()


def test_run_web_falls_back_to_configured_port(monkeypatch):
    server_cls = MagicMock()
    monkeypatch.setattr(webserver, "Server", server_cls)
    monkeypatch.setattr(config_module, "load", lambda: {"web_port": 1234})

    webserver.run_web()

    _, kwargs = server_cls.call_args
    assert kwargs["port"] == 1234


def test_run_web_command_uses_module_invocation(monkeypatch):
    server_cls = MagicMock()
    monkeypatch.setattr(webserver, "Server", server_cls)
    monkeypatch.setattr(config_module, "load", lambda: {"web_port": 8000})

    webserver.run_web(port=8000)

    (command,), _ = server_cls.call_args
    assert command == shlex.join([sys.executable, "-m", "flyexit"])
