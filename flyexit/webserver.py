"""Serve the existing Textual TUI over HTTP via textual-serve."""

from __future__ import annotations

import shlex
import sys

from textual_serve.server import Server

from flyexit import config


def run_web(port: int | None = None) -> None:
    """Serve the TUI in a browser on *port* (default: configured web_port).

    Each browser connection gets a fresh subprocess running the plain TUI
    (no flags), proxied over a websocket — the app itself is unmodified.
    Invoked via `-m flyexit` so it works identically from a source checkout
    or an installed tool, with no dependency on a `main.py` file existing.
    """
    if port is None:
        port = config.load()["web_port"]

    command = shlex.join([sys.executable, "-m", "flyexit"])
    Server(command, port=port).serve()
