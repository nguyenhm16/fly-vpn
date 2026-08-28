"""CLI entry-point — dispatches to the app / watchdog / setup-acl / web / daemon."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

_USAGE = """\
fly-vpn — ephemeral Tailscale exit node on Fly.io

Usage:
  fly-vpn                            Launch the interactive terminal UI (default)
  fly-vpn --start                    Launch a session headlessly (no UI)
  fly-vpn --stop                     Tear down the current session
  fly-vpn --status                   Print current status/configuration
  fly-vpn --web [--port N]           Serve the TUI in a browser (default port 8000)
  fly-vpn --daemon-install [--port N]
                                      Install a launchd background daemon serving --web
  fly-vpn --daemon-uninstall         Remove the launchd background daemon
  fly-vpn --watchdog                 Headless orphaned-app cleanup (for cron/launchd)
  fly-vpn --setup-acl                Idempotent Tailscale ACL setup
  fly-vpn --stats                    Print session history from SQLite
  fly-vpn --help, -h                 Show this help
"""


def _port_from_argv() -> int | None:
    if "--port" in sys.argv:
        return int(sys.argv[sys.argv.index("--port") + 1])
    return None


def main() -> None:
    """Entry-point for the CLI."""

    if "--help" in sys.argv or "-h" in sys.argv:
        print(_USAGE, end="")
        return

    load_dotenv(Path.home() / ".fly_vpn.env")
    load_dotenv()  # back-compat: repo-local .env for existing dev checkouts

    if "--watchdog" in sys.argv:
        from flyexit.watchdog import run_watchdog

        run_watchdog()
        return

    if "--setup-acl" in sys.argv:
        from flyexit.acl_setup import run_setup_acl

        run_setup_acl()
        return

    if "--stats" in sys.argv:
        from flyexit.usage_db import print_stats

        print_stats()
        return

    if "--start" in sys.argv:
        from flyexit.headless import run_start

        run_start()
        return

    if "--stop" in sys.argv:
        from flyexit.headless import run_stop

        run_stop()
        return

    if "--status" in sys.argv:
        from flyexit.headless import run_status

        run_status()
        return

    if "--web" in sys.argv:
        from flyexit.webserver import run_web

        run_web(_port_from_argv())
        return

    if "--daemon-install" in sys.argv:
        from flyexit.daemon import install_daemon

        install_daemon(_port_from_argv())
        return

    if "--daemon-uninstall" in sys.argv:
        from flyexit.daemon import uninstall_daemon

        uninstall_daemon()
        return

    from flyexit.app import FlyVPNApp

    app = FlyVPNApp()
    app.run()
