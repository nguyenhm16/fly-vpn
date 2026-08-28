"""Textual TUI application for Fly VPN.

This module is a **pure UI shell**.  All business logic (auth checks,
Fly API calls, Tailscale connection) lives in :mod:`flyexit.session`.
The app only reads structured results and formats them for display.
"""

from __future__ import annotations

import atexit
import os
import signal
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    RichLog,
    Select,
    Sparkline,
    Static,
)

from flyexit import config, keystore
from flyexit.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_ORG,
    DEFAULT_VM_MEMORY,
    FLY_REGIONS,
    TS_EXIT_HOSTNAME,
    VM_MEMORY_OPTIONS,
)
from flyexit.session import (
    ConnectStatus,
    LaunchResult,
    LaunchStatus,
    PreflightStatus,
    VPNSession,
)
from flyexit.settings_screen import SettingsScreen
from flyexit.styles import APP_CSS


def _build_session() -> VPNSession:
    """Construct a VPNSession using keystore + env-var fallbacks.

    Keystore (Settings UI) wins when both are set, matching
    ``fly_api.resolve_token()``'s precedence for the Fly token — otherwise
    a leftover ``.env``/env-var value would silently override any fix made
    in the Settings screen.
    """
    ts_auth_key = keystore.get("ts_auth_key") or os.environ.get("TAILSCALE_AUTHKEY", "")
    ts_api_key = keystore.get("ts_api_key") or os.environ.get("TAILSCALE_API_KEY", "")
    ts_login_server = os.environ.get("TS_LOGIN_SERVER", "")
    ts_tailnet = keystore.get("ts_tailnet") or os.environ.get("TAILSCALE_TAILNET", "")
    return VPNSession(
        ts_auth_key=ts_auth_key,
        ts_api_key=ts_api_key,
        ts_login_server=ts_login_server,
        ts_tailnet=ts_tailnet,
    )


class FlyVPNApp(App[None]):
    """Ephemeral Tailscale exit-node launcher on Fly.io."""

    TITLE = "Fly VPN"
    SUB_TITLE = "Tailscale Exit Node on Fly.io"
    CSS = APP_CSS

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("l", "launch", "Launch", priority=True),
        Binding("s", "stop", "Stop", priority=True),
        Binding("c", "settings", "Settings", priority=True),
        Binding("t", "toggle_dark", "Theme", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._cfg = config.load()
        self._session = _build_session()
        self._launching = False
        self._stopping = False
        self._quitting = False
        self._refreshing = False
        self._session_detection_ran = False

        atexit.register(self._session.emergency_cleanup)

    def _on_signal(self, signum: int, _frame: object) -> None:
        self._session.emergency_cleanup()
        raise SystemExit(128 + signum)

    def on_mount(self) -> None:
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGHUP, self._on_signal)

        log = self._rich_log
        log.write("[bold green]🛡  Fly VPN[/] initialized")
        log.write("")
        self._refresh_stats()
        self.set_interval(1, self._refresh_stats)

        from flyexit.fly_api import resolve_token

        if not resolve_token():
            log.write("[bold yellow]⚠  No Fly.io API token found.[/]")
            log.write("Press [bold]c[/] to open Settings and add one.")

        if not self._session.has_auth:
            log.write("[bold red]⚠  No Tailscale auth configured![/]")
            log.write(
                "Set [bold]TAILSCALE_API_KEY[/] or [bold]TAILSCALE_AUTHKEY[/]"
                " in Settings ([bold]c[/]) or your .env file."
            )

        self._refresh_session_state()

    @on(Button.Pressed, "#btn-refresh")
    def _handle_refresh(self) -> None:
        if self._launching or self._stopping or self._refreshing:
            return
        self._log("[dim]🔄 Refreshing…[/]")
        self._refresh_session_state(manual=True)

    @work(thread=True)
    def _refresh_session_state(self, *, manual: bool = False) -> None:
        """Sync this front-end's view with the real Fly app state.

        Every front-end (terminal TUI, each --web/--daemon browser
        connection, `--start`/`--stop`) is a separate process with no
        shared in-memory state — this is the only way one of them learns
        what another did. Runs automatically on startup (also gating
        Launch until it completes — otherwise a click landing before this
        finishes could launch concurrently with a session started
        elsewhere, corrupting both) and on demand via the Refresh button.
        """
        from flyexit.fly_ops import app_exists

        self._refreshing = True
        app_name = self._cfg.get("app_name", DEFAULT_APP_NAME)
        try:
            running = app_exists(app_name)
        except Exception:  # noqa: BLE001
            self._refreshing = False
            if manual:
                self.call_from_thread(
                    self._log, "[bold red]⚠  Couldn't reach Fly.io API to refresh.[/]"
                )
            return
        finally:
            self._session_detection_ran = True
            self._refreshing = False

        was_active = self._session.is_active

        if running and not was_active:
            self._session.attach(app_name)
            self.call_from_thread(
                self._log,
                f"[dim]🔎 Detected an already-running session"
                f" ([bold]{app_name}[/bold])[/]",
            )
            self.call_from_thread(self._set_buttons, launching=True)
            self.call_from_thread(
                self._set_status, "🟢 Session already running — press Stop to end"
            )
            return

        if not running and was_active:
            self._session.detach()
            self.call_from_thread(
                self._log, "[dim]🔌 Session ended elsewhere — no longer running.[/]"
            )
            self.call_from_thread(self._set_buttons, launching=False)
            self.call_from_thread(self._set_status, "Ready")
            return

        if manual:
            state = "still running" if running else "still nothing running"
            self.call_from_thread(self._log, f"[dim]✔ Refreshed — {state}.[/]")

        if not running and self._session.has_auth:
            # Confirmed nothing is running — safe to allow Launch now.
            self.call_from_thread(
                lambda: setattr(
                    self.query_one("#btn-launch", Button), "disabled", False
                )
            )

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            with Container(id="controls"), Horizontal(id="top-row"):
                with Vertical(id="region-col"):
                    yield Select(
                        [(f"{flag}  {code}", code) for code, flag in FLY_REGIONS],
                        value=self._cfg.get("region", "ams"),
                        id="region-select",
                    )
                    yield Select(
                        [(label, mb) for mb, label in VM_MEMORY_OPTIONS],
                        value=self._cfg.get("vm_memory", DEFAULT_VM_MEMORY),
                        id="memory-select",
                    )
                    with Horizontal(id="button-row"):
                        yield Button(
                            "🚀 Launch",
                            variant="success",
                            id="btn-launch",
                            disabled=True,  # enabled once startup check clears
                        )
                        yield Button(
                            "🛑 Stop",
                            variant="error",
                            id="btn-stop",
                            disabled=True,
                        )
                with Vertical(id="stats-col"):
                    yield Static("", id="stats-text")
                    yield Sparkline([], id="cost-spark")
                    with Horizontal(id="refresh-row"):
                        yield Button("🔄 Refresh", variant="default", id="btn-refresh")
            yield Static("Ready", id="status-bar")
            with Container(id="log-box"):
                yield RichLog(highlight=True, markup=True, id="log")
        yield Footer()

    @property
    def _rich_log(self) -> RichLog:
        return self.query_one("#log", RichLog)

    def _log(self, msg: str) -> None:
        self._rich_log.write(msg)

    def _set_status(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)

    def _set_buttons(self, *, launching: bool) -> None:
        self.query_one("#btn-launch", Button).disabled = launching
        self.query_one("#btn-stop", Button).disabled = not launching

    def _refresh_stats(self) -> None:
        try:
            from flyexit.usage_db import (
                format_cost,
                format_duration,
                get_daily_costs,
                get_live_cost,
                get_stats,
            )

            stats = get_stats()
            total_s = stats.total_seconds
            total_c = stats.total_cost

            sid = self._session._db_session_id
            live_suffix = ""
            if sid is not None:
                live_dur, live_cost = get_live_cost(sid)
                total_s += live_dur
                total_c += live_cost
                live_suffix = "  [bold yellow]⚡ live[/]"

            if stats.total_sessions > 0 or sid is not None:
                self.query_one("#stats-text", Static).update(
                    f"[bold]📊 Usage[/]  "
                    f"{format_duration(total_s)} · "
                    f"{format_cost(total_c)}"
                    f"{live_suffix}"
                )
                self.query_one("#cost-spark", Sparkline).data = get_daily_costs()
            else:
                self.query_one("#stats-text", Static).update("[dim]No sessions yet[/]")
                self.query_one("#cost-spark", Sparkline).data = []
        except Exception:  # noqa: BLE001, S110
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_launch(self) -> None:
        self._do_launch()

    def action_stop(self) -> None:
        self._do_stop()

    def action_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._on_settings_closed)

    def action_quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        if self._session.is_active:
            self._set_status("⏳ Cleaning up before exit…")
            self._log("[dim]🧹 Cleaning up before exit…[/]")
        self._run_quit_teardown()

    @work(thread=True)
    def _run_quit_teardown(self) -> None:
        try:
            app_name, ok = self._session.teardown()
            self._log_teardown(app_name, ok)
        finally:
            self.exit()

    def _on_settings_closed(self, saved: bool) -> None:
        """Re-initialise the session if keys were updated."""
        if not saved:
            return
        self._session.emergency_cleanup()
        atexit.unregister(self._session.emergency_cleanup)
        self._session = _build_session()
        atexit.register(self._session.emergency_cleanup)
        self._log("[dim]🔑 Credentials updated — session restarted.[/]")

        from flyexit.fly_api import resolve_token

        if resolve_token() and self._session.has_auth:
            self.query_one("#btn-launch", Button).disabled = False

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#btn-launch")
    def _handle_launch(self) -> None:
        self._do_launch()

    @on(Button.Pressed, "#btn-stop")
    def _handle_stop(self) -> None:
        self._do_stop()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def _do_launch(self) -> None:
        if self._launching:
            return
        if self._session.is_active:
            self._log("[dim]Already running[/]")
            return
        self._launching = True
        self._set_buttons(launching=True)
        self._set_status("⏳ Preparing…")
        self._log("[dim]🔄 Starting launch sequence…[/]")
        self._run_launch()

    @work(thread=True)
    def _run_launch(self) -> None:
        try:
            app_name = self._cfg.get("app_name", DEFAULT_APP_NAME)
            org = self._cfg.get("org", DEFAULT_ORG)

            pf = self._session.preflight(app_name, org)
            if pf.switched_tailnet:
                self.call_from_thread(
                    self._log,
                    f"[dim]🔀 Switched to Tailscale tailnet"
                    f" [bold]{pf.switched_tailnet}[/bold][/]",
                )
            if pf.username:
                self.call_from_thread(
                    self._log, f"[dim]Authenticated as {pf.username}[/]"
                )

            if pf.status is PreflightStatus.TAILSCALE_MISSING:
                self.call_from_thread(
                    self._log,
                    f"[bold red]❌ {pf.error}[/]\n"
                    "[dim]  → [link=https://tailscale.com/download]"
                    "tailscale.com/download[/link][/]",
                )
                return

            if pf.status is not PreflightStatus.OK:
                self.call_from_thread(self._log, f"[bold red]⚠  {pf.error}[/]")
                return

            app_name = pf.app_name or app_name
            self._cfg["app_name"] = app_name
            self.call_from_thread(
                self._log, f"[dim]App [bold]{app_name}[/bold] ready ✅[/]"
            )

            region = self.query_one("#region-select", Select).value
            if region is Select.BLANK:
                region = self._cfg.get("region", "ams")
            region = str(region)
            self._cfg["region"] = region

            mem_val = self.query_one("#memory-select", Select).value
            vm_memory = (
                int(mem_val)
                if mem_val is not Select.BLANK
                else self._cfg.get("vm_memory", DEFAULT_VM_MEMORY)
            )
            self._cfg["vm_memory"] = vm_memory
            config.save(self._cfg)

            self.call_from_thread(self._set_buttons, launching=True)
            self.call_from_thread(
                self._set_status,
                f"🔄 Launching in {region} ({vm_memory} MB)…",
            )
            self.call_from_thread(
                self._log,
                f"\n[bold cyan]>>> Launching exit node in"
                f" [yellow]{region}[/yellow]"
                f" ({vm_memory} MB)…[/]",
            )

            result = self._session.launch(
                app_name,
                region,
                vm_memory=vm_memory,
                on_output=lambda line: self.call_from_thread(self._log, line),
            )

            if result.status is LaunchStatus.OK:
                self.call_from_thread(
                    self._log, "[bold green]✅ Node launched successfully![/]"
                )
                self.call_from_thread(self._set_status, f"✅ Running in {region}")
                self._show_connect_result(region)
                return

            self._log_launch_error(result)
            self.call_from_thread(self._log, "[dim]🧹 Cleaning up remote resources…[/]")
            app_d, ok = self._session.teardown()
            self._log_teardown(app_d, ok)
        finally:
            self._launching = False
            if not self._session.is_active:
                self.call_from_thread(self._set_buttons, launching=False)
                self.call_from_thread(self._set_status, "Ready")

    def _show_connect_result(self, region: str) -> None:
        self.call_from_thread(
            self._log,
            f"[dim]⏳ Waiting for [bold]{TS_EXIT_HOSTNAME}[/bold]"
            " to appear in tailnet…[/]",
        )
        self.call_from_thread(
            self._set_status, f"⏳ Waiting for exit node in {region}…"
        )

        status = self._session.wait_and_connect()

        if status is ConnectStatus.CONNECTED:
            self.call_from_thread(
                self._log,
                f"[bold green]🔗 Connected![/] Traffic routed"
                f" through [bold]{TS_EXIT_HOSTNAME}[/]"
                f" ({region})\n"
                "[dim]  Press [bold]Stop[/bold] (or [bold]s[/bold])"
                " to disconnect and clean up.[/]",
            )
            self.call_from_thread(
                self._set_status,
                f"🟢 VPN active via {region} — press Stop to end",
            )
        elif status is ConnectStatus.TIMEOUT:
            self.call_from_thread(
                self._log,
                "[yellow]⚠  Exit node didn't appear in time. "
                "Connect manually via Tailscale.[/]\n"
                "[dim]  Press [bold]Stop[/bold] (or [bold]s[/bold])"
                " to terminate and clean up.[/]",
            )
            self.call_from_thread(
                self._set_status, f"🟡 Running in {region} — manual connect needed"
            )
        else:
            self.call_from_thread(
                self._log,
                "[yellow]⚠  Node is online but auto-connect failed.\n"
                f"  Try manually: tailscale set --exit-node={TS_EXIT_HOSTNAME}[/]",
            )
            self.call_from_thread(
                self._set_status, f"🟡 Running in {region} — manual connect needed"
            )

    def _do_stop(self) -> None:
        if self._stopping:
            return
        if self._session.is_active:
            self._stopping = True
            self._launching = False
            self._set_buttons(launching=True)
            self.query_one("#btn-stop", Button).disabled = True
            self._set_status("⏳ Stopping…")
            self._log("[bold yellow]⏹  Stopping node…[/]")
            self._run_stop()
        else:
            self._log("[dim]Nothing to stop[/]")

    @work(thread=True)
    def _run_stop(self) -> None:
        try:
            app_name, ok = self._session.teardown()
            self.call_from_thread(self._log, "[dim]🔌 Disconnected from exit node[/]")
            self._log_teardown(app_name, ok)
            if ok and app_name:
                if self._session._client is not None:
                    self.call_from_thread(
                        self._log, "[dim]🗑  Tailscale node removed from tailnet.[/]"
                    )
                else:
                    self.call_from_thread(
                        self._log,
                        "[dim]💨 Tailscale ephemeral node will auto-remove"
                        " within a few minutes.[/]",
                    )
            try:
                from flyexit.usage_db import format_cost, format_duration, get_stats

                stats = get_stats()
                if stats.total_sessions > 0:
                    self.call_from_thread(
                        self._log,
                        f"[dim]💰 {stats.total_sessions} session(s),"
                        f" {format_duration(stats.total_seconds)},"
                        f" {format_cost(stats.total_cost)} spent[/]",
                    )
            except Exception:  # noqa: BLE001, S110
                pass
            self.call_from_thread(self._refresh_stats)
        finally:
            self._stopping = False
            if not self._session.is_active:
                self.call_from_thread(self._set_buttons, launching=False)
                self.call_from_thread(self._set_status, "Ready")
            else:
                self.call_from_thread(self._set_buttons, launching=True)
                self.call_from_thread(
                    self._set_status, "⚠️ Stop failed; tunnel still running"
                )

    def _log_launch_error(self, result: LaunchResult) -> None:
        if result.status is LaunchStatus.ERROR:
            self.call_from_thread(self._log, f"[bold red]❌ Error: {result.error}[/]")
        else:  # LaunchStatus.MACHINE_FAILED
            if result.error:
                self.call_from_thread(
                    self._log, f"[bold red]❌ Machine failed:[/] {result.error}"
                )
            if result.hint:
                self.call_from_thread(self._log, result.hint)

    def _log_teardown(self, app_name: str | None, ok: bool) -> None:
        if not app_name:
            return
        msg = (
            f"[bold green]🗑  App [bold]{app_name}[/bold] deleted (no charges)[/]"
            if ok
            else f"[yellow]⚠  Could not delete app {app_name}[/]"
        )
        self.call_from_thread(self._log, msg)
