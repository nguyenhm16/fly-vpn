"""Headless session control — launch or tear down a session without the TUI."""

from __future__ import annotations

import re
import signal
import sys

from flyexit import config
from flyexit.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_ORG,
    DEFAULT_REGION,
    DEFAULT_VM_MEMORY,
)
from flyexit.fly_ops import app_exists
from flyexit.session import ConnectStatus, LaunchStatus, PreflightStatus
from flyexit.tailscale import disconnect_exit_node


def _build_session():
    from flyexit.app import _build_session as build_session

    return build_session()


def _plain(text: str) -> str:
    """Strip Rich [tag] markup from a message meant for the TUI log."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


def run_start() -> None:
    """Launch a Fly.io exit node and connect Tailscale, headlessly."""
    cfg = config.load()
    session = _build_session()

    if not session.has_auth:
        print("Error: no Tailscale credentials configured.")
        print(
            "Set TAILSCALE_API_KEY or TAILSCALE_AUTHKEY, or run the TUI once"
            " to configure Settings."
        )
        sys.exit(1)

    def _cleanup_and_exit(signum: int, _frame: object) -> None:
        print("\nInterrupted — cleaning up…")
        session.emergency_cleanup()
        sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _cleanup_and_exit)
    signal.signal(signal.SIGTERM, _cleanup_and_exit)

    app_name = cfg.get("app_name", DEFAULT_APP_NAME)
    org = cfg.get("org", DEFAULT_ORG)
    region = cfg.get("region", DEFAULT_REGION)
    vm_memory = cfg.get("vm_memory", DEFAULT_VM_MEMORY)

    print("Starting launch sequence…")
    pf = session.preflight(app_name, org)

    if pf.switched_tailnet:
        print(f"Switched to Tailscale tailnet {pf.switched_tailnet}")
    if pf.username:
        print(f"Authenticated as {pf.username}")

    if pf.status is not PreflightStatus.OK:
        print(f"Error: {_plain(pf.error)}")
        sys.exit(1)

    app_name = pf.app_name or app_name
    print(f"App {app_name} ready")
    print(f"Launching in {region} ({vm_memory} MB)…")

    result = session.launch(
        app_name,
        region,
        vm_memory=vm_memory,
        on_output=lambda line: print(_plain(line)),
    )

    if result.status is not LaunchStatus.OK:
        if result.error:
            print(f"Error: {result.error}")
        if result.hint:
            print(_plain(result.hint))
        print("Cleaning up remote resources…")
        session.teardown()
        sys.exit(1)

    print("Node launched successfully.")
    print("Waiting for exit node to appear in tailnet…")
    status = session.wait_and_connect()

    if status is ConnectStatus.CONNECTED:
        print(f"Connected — traffic routed through the exit node ({region}).")
    elif status is ConnectStatus.TIMEOUT:
        print("Exit node didn't appear in time. Connect manually via Tailscale.")
    else:
        print(
            "Node is online but auto-connect failed. Try manually:"
            " tailscale set --exit-node=fly-vpn-exit"
        )

    print("Run 'fly-vpn --stop' to disconnect and clean up.")


def run_stop() -> None:
    """Tear down the current session's Fly app and disconnect Tailscale."""
    cfg = config.load()
    app_name = cfg.get("app_name", DEFAULT_APP_NAME)

    if not app_exists(app_name):
        disconnect_exit_node()
        print("Nothing running.")
        return

    session = _build_session()
    session.attach(app_name)

    print("Stopping node…")
    _, ok = session.teardown()
    print("Disconnected from exit node")

    if not ok:
        print(f"Error: failed to destroy {app_name} — check manually.")
        sys.exit(1)

    print(f"Destroyed {app_name}")
    if session._client is not None:
        print("Tailscale node removed from tailnet.")
    else:
        print("Tailscale ephemeral node will auto-remove within a few minutes.")
