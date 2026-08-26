"""Watchdog — headless check that destroys orphaned Fly apps to prevent charges."""

from __future__ import annotations

import logging
import sys

from flyexit import config
from flyexit.constants import DEFAULT_APP_NAME
from flyexit.fly_ops import app_exists, destroy_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [fly-vpn-watchdog] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def run_watchdog() -> None:
    """Main watchdog routine — check, kill, destroy, exit."""
    cfg = config.load()
    app_name = cfg.get("app_name", DEFAULT_APP_NAME)

    log.info("Checking for orphaned app '%s'…", app_name)

    if not app_exists(app_name):
        log.info("App '%s' does not exist — nothing to do. ✅", app_name)
        sys.exit(0)

    log.warning(
        "App '%s' found! Cleaning up to prevent charges…",
        app_name,
    )

    if destroy_app(app_name):
        log.info("App '%s' destroyed successfully. 🗑  No charges.", app_name)
    else:
        log.error("Failed to destroy app '%s'! Check manually.", app_name)
        sys.exit(1)
