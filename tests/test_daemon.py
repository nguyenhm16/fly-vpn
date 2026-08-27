"""Tests for flyexit.daemon launchd lifecycle management."""

from __future__ import annotations

import plistlib
from unittest.mock import MagicMock

from flyexit import daemon

_TAILSCALE = {"tailscale": "/opt/homebrew/bin/tailscale"}


def _which(mapping):
    return lambda name: mapping.get(name)


def test_install_daemon_prefers_installed_tool_binary(monkeypatch, tmp_path):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    log_path = tmp_path / "fly-vpn-daemon.log"
    run_mock = MagicMock()

    monkeypatch.setattr(
        daemon.shutil,
        "which",
        _which({**_TAILSCALE, "fly-vpn": "/Users/me/.local/bin/fly-vpn"}),
    )
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon, "_log_path", lambda: log_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon()

    with plist_path.open("rb") as f:
        plist = plistlib.load(f)

    assert plist["Label"] == daemon._LABEL
    assert plist["ProgramArguments"] == ["/Users/me/.local/bin/fly-vpn", "--web"]
    assert plist["WorkingDirectory"] == str(daemon.Path.home())
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] is True
    assert plist["StandardOutPath"] == str(log_path)
    assert plist["EnvironmentVariables"]["PATH"].startswith("/opt/homebrew/bin")

    run_mock.assert_called_once_with(
        ["launchctl", "load", "-w", str(plist_path)], check=True
    )


def test_install_daemon_resolves_tailscale_dir_dynamically(monkeypatch, tmp_path):
    """PATH should reflect wherever tailscale actually is, not a guessed prefix."""
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    log_path = tmp_path / "fly-vpn-daemon.log"

    monkeypatch.setattr(
        daemon.shutil,
        "which",
        _which(
            {
                "tailscale": "/some/unusual/prefix/bin/tailscale",
                "fly-vpn": "/Users/me/.local/bin/fly-vpn",
            }
        ),
    )
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon, "_log_path", lambda: log_path)
    monkeypatch.setattr(daemon.subprocess, "run", MagicMock())

    daemon.install_daemon()

    with plist_path.open("rb") as f:
        plist = plistlib.load(f)

    assert plist["EnvironmentVariables"]["PATH"].startswith("/some/unusual/prefix/bin")


def test_install_daemon_missing_tailscale_suggests_brew(monkeypatch, tmp_path, capsys):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    run_mock = MagicMock()

    monkeypatch.setattr(
        daemon.shutil, "which", _which({"brew": "/opt/homebrew/bin/brew"})
    )
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon()

    assert not plist_path.exists()
    run_mock.assert_not_called()
    assert "brew install tailscale" in capsys.readouterr().out


def test_install_daemon_missing_tailscale_no_brew_suggests_download(
    monkeypatch, tmp_path, capsys
):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    run_mock = MagicMock()

    monkeypatch.setattr(daemon.shutil, "which", _which({}))
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon()

    assert not plist_path.exists()
    run_mock.assert_not_called()
    assert "tailscale.com/download" in capsys.readouterr().out


def test_install_daemon_forwards_port(monkeypatch, tmp_path):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    log_path = tmp_path / "fly-vpn-daemon.log"

    monkeypatch.setattr(
        daemon.shutil,
        "which",
        _which({**_TAILSCALE, "fly-vpn": "/Users/me/.local/bin/fly-vpn"}),
    )
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon, "_log_path", lambda: log_path)
    monkeypatch.setattr(daemon.subprocess, "run", MagicMock())

    daemon.install_daemon(port=9999)

    with plist_path.open("rb") as f:
        plist = plistlib.load(f)

    assert plist["ProgramArguments"] == [
        "/Users/me/.local/bin/fly-vpn",
        "--web",
        "--port",
        "9999",
    ]


def test_install_daemon_unloads_existing_job_before_reinstalling(monkeypatch, tmp_path):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    plist_path.write_bytes(b"placeholder")  # simulates an already-installed job
    log_path = tmp_path / "fly-vpn-daemon.log"
    run_mock = MagicMock()

    monkeypatch.setattr(
        daemon.shutil,
        "which",
        _which({**_TAILSCALE, "fly-vpn": "/Users/me/.local/bin/fly-vpn"}),
    )
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon, "_log_path", lambda: log_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon(port=7777)

    assert run_mock.call_args_list == [
        (
            (["launchctl", "unload", "-w", str(plist_path)],),
            {"check": False},
        ),
        (
            (["launchctl", "load", "-w", str(plist_path)],),
            {"check": True},
        ),
    ]


def test_install_daemon_falls_back_to_uv_run_for_dev_checkout(monkeypatch, tmp_path):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    log_path = tmp_path / "fly-vpn-daemon.log"
    run_mock = MagicMock()

    monkeypatch.setattr(
        daemon.shutil,
        "which",
        _which({**_TAILSCALE, "uv": "/opt/homebrew/bin/uv"}),
    )
    monkeypatch.setattr(daemon, "_plist_path", lambda: plist_path)
    monkeypatch.setattr(daemon, "_log_path", lambda: log_path)
    monkeypatch.setattr(daemon.subprocess, "run", run_mock)

    daemon.install_daemon()

    with plist_path.open("rb") as f:
        plist = plistlib.load(f)

    assert plist["ProgramArguments"] == [
        "/opt/homebrew/bin/uv",
        "run",
        "--project",
        str(daemon._repo_root()),
        "fly-vpn",
        "--web",
    ]
    assert plist["WorkingDirectory"] == str(daemon._repo_root())


def test_install_daemon_missing_uv_and_fly_vpn(monkeypatch, tmp_path, capsys):
    plist_path = tmp_path / "dev.flyvpn.daemon.plist"
    run_mock = MagicMock()

    monkeypatch.setattr(daemon.shutil, "which", _which(dict(_TAILSCALE)))
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
