"""Serve the existing Textual TUI over HTTP via textual-serve."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from textual_serve.server import Server

from flyexit import config

_TEMPLATES_PATH = Path(__file__).resolve().parent / "web_templates"


def run_web(port: int | None = None) -> None:
    """Serve the TUI in a browser on *port* (default: configured web_port).

    Each browser connection gets a fresh subprocess running the plain TUI
    (no flags), proxied over a websocket — the app itself is unmodified.
    Invoked via `-m flyexit` so it works identically from a source checkout
    or an installed tool, with no dependency on a `main.py` file existing.

    Uses a custom app_index.html (templates_path) that tries to close the
    browser window/tab outright when the app quits, instead of textual-
    serve's default "Session ended." + Restart dialog — this is what makes
    quitting from inside a Safari "Add to Dock" web app actually quit that
    app. Falls back to the original dialog if window.close() is blocked
    (an ordinary browser tab the script didn't open).
    """
    if port is None:
        port = config.load()["web_port"]

    command = shlex.join([sys.executable, "-m", "flyexit"])
    Server(command, port=port, templates_path=_TEMPLATES_PATH).serve()
