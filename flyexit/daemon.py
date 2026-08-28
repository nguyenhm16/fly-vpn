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

from flyexit import config

_LABEL = "dev.flyvpn.daemon"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"


def _log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "fly-vpn-daemon.log"


def _tailscale_dir() -> str | None:
    """Directory containing the `tailscale` CLI, resolved from this PATH."""
    tailscale = shutil.which("tailscale")
    if tailscale is None:
        return None
    return str(Path(tailscale).parent)


def _tailscale_missing_hint() -> str:
    if shutil.which("brew"):
        install_hint = "  brew install tailscale"
    else:
        install_hint = "  https://tailscale.com/download"
    return (
        "Could not find the 'tailscale' CLI on PATH. Install it, e.g.:\n"
        f"{install_hint}\n"
        "then try again."
    )


def _daemon_path(tailscale_dir: str) -> str:
    """PATH for the launchd job's environment.

    launchd runs jobs with a minimal default PATH (no Homebrew), so
    `tailscale` — normally found via the user's shell PATH — would
    otherwise be invisible to the daemon and anything it spawns (including
    the per-browser-connection subprocess in --web mode). Uses tailscale's
    actual resolved location rather than guessing common install
    prefixes, so it works regardless of how/where it was installed.
    """
    return ":".join([tailscale_dir, "/usr/bin", "/bin", "/usr/sbin", "/sbin"])


def _web_command(port: int) -> tuple[list[str], Path]:
    """Return (ProgramArguments, WorkingDirectory) for the launchd job.

    Prefers the standalone `fly-vpn` tool on PATH (installed via
    `uv tool install`, independent of any repo checkout). Falls back to
    `uv run --project <repo>` for dev checkouts that haven't installed it
    as a tool.
    """
    port_args = ["--port", str(port)]

    fly_vpn = shutil.which("fly-vpn")
    if fly_vpn:
        return [fly_vpn, "--web", *port_args], Path.home()

    uv_path = shutil.which("uv")
    if uv_path is None:
        msg = (
            "Could not find 'fly-vpn' or 'uv' on PATH. Install uv from "
            "https://docs.astral.sh/uv/ and try again."
        )
        raise RuntimeError(msg)

    repo_root = _repo_root()
    return (
        [uv_path, "run", "--project", str(repo_root), "fly-vpn", "--web", *port_args],
        repo_root,
    )


def install_daemon(port: int | None = None) -> None:
    """Write and load a launchd agent that runs `fly-vpn --web` in the background."""
    tailscale_dir = _tailscale_dir()
    if tailscale_dir is None:
        print(_tailscale_missing_hint())
        return

    # Persist an explicit --port so it becomes the new default — this is
    # also what makes `fly-vpn --status` report the port the daemon is
    # actually running on, rather than always the stock default.
    cfg = config.load()
    if port is None:
        port = cfg["web_port"]
    elif port != cfg["web_port"]:
        cfg["web_port"] = port
        config.save(cfg)

    try:
        program_arguments, working_directory = _web_command(port)
    except RuntimeError as exc:
        print(exc)
        return

    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    plist = {
        "Label": _LABEL,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(working_directory),
        "RunAtLoad": True,
        "KeepAlive": True,
        "EnvironmentVariables": {
            "PATH": _daemon_path(tailscale_dir),
            "FLY_NO_UPDATE_CHECK": "1",
        },
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }

    plist_path = _plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    if plist_path.exists():
        # Re-installing (e.g. to change the port): launchd won't pick up
        # new ProgramArguments for an already-loaded job unless it's
        # unloaded first.
        subprocess.run(["launchctl", "unload", "-w", str(plist_path)], check=False)

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
