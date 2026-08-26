"""Persistent configuration helpers — backed by the SQLite keystore."""

from __future__ import annotations

import secrets
from typing import Any

from flyexit import keystore
from flyexit.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_ORG,
    DEFAULT_REGION,
    DEFAULT_VM_MEMORY,
)

_DEFAULTS: dict[str, Any] = {
    "region": DEFAULT_REGION,
    "app_name": DEFAULT_APP_NAME,
    "org": DEFAULT_ORG,
    "vm_memory": DEFAULT_VM_MEMORY,
}


def load() -> dict[str, Any]:
    """Read config from the keystore, falling back to built-in defaults.

    ``app_name`` is special-cased: Fly.io app names are globally unique
    across *all* accounts, so the literal ``DEFAULT_APP_NAME`` can never be
    safely reused as-is (it's baked into every install of this tool, and
    can permanently collide with someone else's app). The first time it's
    seen, a random per-install suffix is generated and persisted so this
    installation gets a name of its own from then on.
    """
    result: dict[str, Any] = {}
    for key, default in _DEFAULTS.items():
        raw = keystore.get(key)
        if raw:
            result[key] = int(raw) if isinstance(default, int) else raw
        else:
            result[key] = default

    if result["app_name"] == DEFAULT_APP_NAME:
        result["app_name"] = f"{DEFAULT_APP_NAME}-{secrets.token_hex(3)}"
        keystore.set("app_name", result["app_name"])

    return result


def save(config: dict[str, Any]) -> None:
    """Persist *config* to the keystore."""
    for key, value in config.items():
        keystore.set(key, str(value))
