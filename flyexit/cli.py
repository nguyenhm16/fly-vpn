"""CLI entry-point — dispatches to the app / watchdog / setup-acl / web / daemon."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


def _port_from_argv() -> int | None:
    if "--port" in sys.argv:
        return int(sys.argv[sys.argv.index("--port") + 1])
    return None


def main() -> None:
    """Entry-point for the CLI."""

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
