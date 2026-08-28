"""Tests for flyexit.cli's flag validation and dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from flyexit import cli


def test_unknown_flag_exits_without_launching_app(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["fly-vpn", "--totally-bogus"])
    app_cls = MagicMock()
    monkeypatch.setattr("flyexit.app.FlyVPNApp", app_cls, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    app_cls.assert_not_called()


def test_unrecognized_bare_word_exits(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["fly-vpn", "strat"])

    with pytest.raises(SystemExit):
        cli.main()


def test_port_value_is_not_treated_as_unknown_flag(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["fly-vpn", "--web", "--port", "9999"])
    run_web = MagicMock()
    monkeypatch.setattr("flyexit.webserver.run_web", run_web)

    cli.main()  # must not raise

    run_web.assert_called_once_with(9999)


def test_help_flag_still_works(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "argv", ["fly-vpn", "--help"])

    cli.main()

    assert "Usage:" in capsys.readouterr().out


def test_no_args_launches_the_tui(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["fly-vpn"])
    app_instance = MagicMock()
    app_cls = MagicMock(return_value=app_instance)
    monkeypatch.setattr("flyexit.app.FlyVPNApp", app_cls, raising=False)

    cli.main()

    app_instance.run.assert_called_once()
