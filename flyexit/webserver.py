"""Serve the existing Textual TUI over HTTP via textual-serve."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from textual_serve.server import Server

from flyexit import config

_MAIN_PY = Path(__file__).resolve().parent.parent / "main.py"


def run_web(port: int | None = None) -> None:
    """Serve the TUI in a browser on *port* (default: configured web_port).

    Each browser connection gets a fresh subprocess running the plain TUI
    (no flags), proxied over a websocket — the app itself is unmodified.
    """
    if port is None:
        port = config.load()["web_port"]

    command = shlex.join([sys.executable, str(_MAIN_PY)])
    Server(command, port=port).serve()
