# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Fly VPN is a Textual TUI app that spins up an ephemeral Tailscale exit node on a Fly.io Machine, auto-connects local traffic to it, and destroys everything on stop. Python 3.14, `uv`-managed, single-package layout (`flyexit/`).

## Commands

```bash
uv sync                                    # install deps (incl. dev group)
uv run fly-vpn                             # run the TUI
uv run python main.py                      # same, via entry-point module
uv run python main.py --watchdog           # headless orphaned-app cleanup
uv run python main.py --setup-acl          # idempotent Tailscale ACL setup
uv run python main.py --stats              # print session history from SQLite

uv run pytest                              # run all tests
uv run pytest tests/test_db.py             # single file
uv run pytest tests/test_db.py::test_name  # single test

uv run ruff check flyexit/ main.py         # lint
uv run ruff format --check flyexit/ main.py  # format check
uv run ruff format flyexit/ main.py        # auto-format
uv build                                   # build wheel (hatchling)
```

CI (`.github/workflows/ci.yml`) runs `uv sync`, `ruff check`, `ruff format --check`, and `uv build` on push/PR to `main`. There is no test step in CI — run `pytest` locally before pushing.

`asyncio_mode = "auto"` is set in `pyproject.toml`, so async test functions don't need `@pytest.mark.asyncio`.

## Architecture

**Layering principle: UI-only app layer + enum-based session orchestration + direct cloud API integration.** No `flyctl` binary dependency — all Fly.io calls go through the Machines REST API directly via `httpx`.

```
main.py              → entry-point; dispatches to app / --watchdog / --setup-acl / --stats
flyexit/app.py        → Textual UI only (FlyVPNApp); calls VPNSession methods, renders results
flyexit/settings_screen.py → credentials UI (Fly token, Tailscale key/authkey/login server)
flyexit/session.py     → VPNSession: owns preflight/launch/connect/teardown orchestration
flyexit/fly_ops.py      → auth check, app create/destroy/cleanup — thin wrappers over fly_api
flyexit/fly_api.py      → FlyAPIClient: raw Machines REST API client (httpx)
flyexit/tailscale.py     → local `tailscale` CLI adapter (connect/disconnect/status, subprocess)
flyexit/tailscale_api.py → Tailscale Admin API client (ACL read/write, auth-key create, device delete)
flyexit/acl_setup.py      → idempotent ACL business logic + --setup-acl CLI entry
flyexit/diagnosis.py       → maps raw Fly API errors to human-readable hints
flyexit/db.py               → unified SQLite connection (~/.fly_vpn.db) + migrations
flyexit/keystore.py          → generic key-value settings table on top of db.py
flyexit/config.py             → typed app config (region, memory, etc.) on top of keystore
flyexit/usage_db.py            → session history logging (start/end, cost) on top of db.py
flyexit/watchdog.py             → headless orphan-app sweep (safety net for --watchdog)
flyexit/constants.py             → region catalogue, timeouts, defaults (no logic)
flyexit/styles.py                 → Textual CSS-like styling constants
```

### Session lifecycle (`session.py`)

`VPNSession` is the single source of business logic; the UI layer (`app.py`) never talks to Fly or Tailscale APIs directly. Flow: `preflight()` → `launch()` → `wait_and_connect()` → ... → `teardown()` (or `emergency_cleanup()` on signal/atexit). Each step returns a dataclass (`PreflightResult`, `LaunchResult`) wrapping a `Status` enum — the UI matches on the enum rather than parsing strings/exceptions. `session.py` re-exports enums/results from `fly_ops` so the UI only needs one import (`from flyexit.session import ...`).

Two Tailscale auth paths coexist in `VPNSession.__init__`: an explicit `ts_auth_key` (manual/Headscale flow), or a `TailscaleAPIClient` built from `ts_api_key` (SaaS flow, mutually exclusive with `ts_login_server`) that auto-generates single-use ephemeral auth keys per launch and deletes the device on teardown.

`emergency_cleanup()` must stay synchronous and exception-free — it runs from signal handlers and `atexit`, outside the Textual event loop.

### Fly.io integration

`fly_api.py` is the only module that speaks HTTP to Fly's Machines API. `fly_ops.py` wraps it with domain operations (`check_auth`, `ensure_app_exists`, `destroy_app`, `cleanup_app_sync`). `ensure_app_exists` unconditionally deletes any existing app with the same name before creating fresh, then retries creation up to 10 times on "already taken" errors to absorb Fly's post-deletion name-propagation lag — this pattern exists because of a known race, don't remove the retry loop without understanding why (see `tests/test_ensure_app_exists.py`).

App names collide globally on Fly.io, across every account — not just within your own. `config.load()` handles this: the first time it sees the literal default app name, it generates a random per-install suffix (`fly-vpn-node-{6 hex chars}`) and persists it, so this installation never shares a name with anyone else's. (An earlier approach derived the suffix from the user's Fly org slug instead — that broke for accounts with zero existing apps, and even when it worked, every default/personal-tier account shares the literal org slug `"personal"`, which just traded one globally-shared name for another.)

### Persistence (`db.py` + friends)

Single unified SQLite database at `~/.fly_vpn.db`, chmod'd `0600` on first creation (it stores API tokens in plaintext in the `settings` table). Schema evolves via an append-only `MIGRATIONS` tuple tracked with `PRAGMA user_version` — **never reorder or edit existing migration entries, only append new ones**. Migrations also absorb legacy state: `003`/`004` one-time-import data from the old `~/.fly_vpn_usage.db` and `~/.fly_vpn_config.json` files (pre-unification), then rename them to `.bak`. `keystore.py`, `config.py`, and `usage_db.py` all build on `db.connect()` rather than opening SQLite directly.

### Concurrency in the UI

`app.py` uses Textual `@work(thread=True)` workers for launch/stop so the UI stays responsive during blocking I/O. `tests/test_launch_stop_race.py` documents two race conditions already fixed here (button-lock flags must be cleared in a `finally` block, and in the correct order relative to `call_from_thread`) — preserve that ordering in any changes to the launch/stop worker flow.

## Linting notes

Ruff config (`pyproject.toml`) enables `S` (bandit/security) and `BLE` (blind-except) rules repo-wide, with `S603`/`S607` (subprocess call security) ignored globally since `tailscale.py`/`fly_ops.py` legitimately shell out. `tests/**` ignores `S101` (assert usage). Blind `except Exception` blocks that intentionally swallow errors (e.g. `session.py`'s usage-log helpers) are annotated `# noqa: BLE001` — match this convention rather than suppressing the rule config-wide.
