"""launchd lifecycle management — run the web UI as a background daemon.

Installs a user LaunchAgent whose `ProgramArguments` invoke ``fly-vpn --web``;
launchd itself supplies "runs in the background" and "restarts on crash"
(`RunAtLoad`/`KeepAlive`) — no separate daemon run-mode is needed in the app.
"""

from __future__ import annotations

import plistlib
import shutil
import subprocess
from pathlib import Path

_LABEL = "dev.flyvpn.daemon"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"


def _log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "fly-vpn-daemon.log"


def install_daemon() -> None:
    """Write and load a launchd agent that runs `fly-vpn --web` in the background."""
    uv_path = shutil.which("uv")
    if uv_path is None:
        print(
            "Could not find the 'uv' command on PATH. Install it from "
            "https://docs.astral.sh/uv/ and try again."
        )
        return

    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    plist = {
        "Label": _LABEL,
        "ProgramArguments": [
            uv_path,
            "run",
            "--project",
            str(_repo_root()),
            "fly-vpn",
            "--web",
        ],
        "WorkingDirectory": str(_repo_root()),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }

    plist_path = _plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "load", "-w", str(plist_path)], check=True)

    print(f"Daemon installed and started — logs at {log_path}")
    print(f"launchd job: {_LABEL} ({plist_path})")


def uninstall_daemon() -> None:
    """Unload and remove the launchd agent, if installed."""
    plist_path = _plist_path()
    if not plist_path.exists():
        print(f"No daemon installed ({_LABEL})")
        return

    subprocess.run(["launchctl", "unload", "-w", str(plist_path)], check=True)
    plist_path.unlink()

    print(f"Daemon uninstalled ({_LABEL})")
