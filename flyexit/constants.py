"""Fly.io region catalogue and application defaults."""

from __future__ import annotations

import os
from typing import Final

DEFAULT_REGION: Final = "ams"
DEFAULT_APP_NAME: Final = "fly-vpn-node"
DEFAULT_ORG: Final = "personal"
DEFAULT_VM_MEMORY: Final = 512  # MB
DEFAULT_WEB_PORT: Final = 8000

# Choices for the memory selector (MB → label).
VM_MEMORY_OPTIONS: Final[list[tuple[int, str]]] = [
    (256, "256 MB"),
    (512, "512 MB"),
    (1024, "1 GB"),
    (2048, "2 GB"),
]

# Fly CLI environment — suppress update prompts.
FLY_ENV: Final[dict[str, str]] = {**os.environ, "FLY_NO_UPDATE_CHECK": "1"}

# Tailscale exit-node settings.
TS_EXIT_HOSTNAME: Final = "fly-vpn-exit"
TS_CONNECT_TIMEOUT: Final = 30  # seconds to wait for node in tailnet
TS_POLL_INTERVAL: Final = 2  # seconds between status polls

# (code, flag + city) - used to populate the region selector.
# Source: https://fly.io/docs/reference/regions/
FLY_REGIONS: Final[list[tuple[str, str]]] = [
    ("ams", "🇳🇱 Amsterdam"),
    ("arn", "🇸🇪 Stockholm"),
    ("cdg", "🇫🇷 Paris"),
    ("fra", "🇩🇪 Frankfurt"),
    ("lhr", "🇬🇧 London"),
    ("dfw", "🇺🇸 Dallas"),
    ("ewr", "🇺🇸 Secaucus"),
    ("iad", "🇺🇸 Ashburn"),
    ("lax", "🇺🇸 Los Angeles"),
    ("ord", "🇺🇸 Chicago"),
    ("sjc", "🇺🇸 San Jose"),
    ("yyz", "🇨🇦 Toronto"),
    ("gru", "🇧🇷 São Paulo"),
    ("bom", "🇮🇳 Mumbai"),
    ("nrt", "🇯🇵 Tokyo"),
    ("sin", "🇸🇬 Singapore"),
    ("syd", "🇦🇺 Sydney"),
    ("jnb", "🇿🇦 Johannesburg"),
]
