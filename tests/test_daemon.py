"""Tests for flyexit.daemon launchd lifecycle management."""

from __future__ import annotations

from unittest.mock import MagicMock

from flyexit import daemon


def test_install_daemon_writes_plist_and_loads(monkeypatch, tmp_path):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    log_path = tmp_path / "fly-vpn-daemon.log"
    run_mock = MagicMock()

    monkeypatch.setattr(daemon.shutil, "which", lambda _: "/opt/homebrew/bin/uv")
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon, "_log_path", lambda: log_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon()

    assert plist_path.exists()
    assert log_path.parent.exists()

    import plistlib

    with plist_path.open("rb") as f:
        plist = plistlib.load(f)

    assert plist["Label"] == daemon._LABEL
    assert plist["ProgramArguments"][0] == "/opt/homebrew/bin/uv"
    assert plist["ProgramArguments"][-2:] == ["fly-vpn", "--web"]
    assert plist["WorkingDirectory"] == str(daemon._repo_root())
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] is True
    assert plist["StandardOutPath"] == str(log_path)

    run_mock.assert_called_once_with(
        ["launchctl", "load", "-w", str(plist_path)], check=True
    )


def test_install_daemon_missing_uv(monkeypatch, tmp_path, capsys):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    run_mock = MagicMock()

    monkeypatch.setattr(daemon.shutil, "which", lambda _: None)
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon()

    assert not plist_path.exists()
    run_mock.assert_not_called()
    assert "uv" in capsys.readouterr().out


def test_uninstall_daemon_removes_plist(monkeypatch, tmp_path):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    plist_path.write_bytes(b"placeholder")
    run_mock = MagicMock()

    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.uninstall_daemon()

    assert not plist_path.exists()
    run_mock.assert_called_once_with(
        ["launchctl", "unload", "-w", str(plist_path)], check=True
    )


def test_uninstall_daemon_noop_when_not_installed(monkeypatch, tmp_path, capsys):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    run_mock = MagicMock()

    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.uninstall_daemon()

    run_mock.assert_not_called()
    assert "No daemon installed" in capsys.readouterr().out
