"""Textual CSS styles for the Fly VPN app."""

APP_CSS = """\
Screen {
    background: $surface;
}

#main {
    margin: 1 2;
}

#controls {
    height: auto;
    padding: 1 2;
    background: $panel;
    border: tall $primary;
    margin-bottom: 1;
}

#top-row {
    height: auto;
}

#region-col {
    width: 1fr;
    height: auto;
}

#stats-col {
    width: 1fr;
    height: auto;
    padding: 0 0 0 2;
}

#stats-text {
    height: 1;
    text-style: bold;
}

#cost-spark {
    height: 1;
    margin-top: 1;
}

#btn-update {
    margin-top: 1;
    width: auto;
    min-width: 12;
    height: 1;
    background: $surface;
    border: none;
    color: $text-muted;
}

#btn-update:hover {
    color: $text;
    background: $panel-lighten-2;
}

#update-row {
    height: auto;
    align: right middle;
}

Sparkline > .sparkline--max-color {
    color: $success;
}

Sparkline > .sparkline--min-color {
    color: $success 20%;
}

#region-select {
    width: 40;
}

#memory-select {
    width: 40;
    margin-top: 1;
}

#button-row {
    height: auto;
    margin-top: 1;
    align: left middle;
}

#btn-launch {
    margin: 0 1 0 0;
}

#btn-stop {
    margin: 0 1;
}

#btn-refresh {
    margin: 0 1;
}

#status-bar {
    height: 1;
    margin: 0 0 1 0;
    padding: 0 2;
    text-align: left;
    color: $text-muted;
    text-style: italic;
}

#log-box {
    border: tall $accent;
    height: 1fr;
    min-height: 10;
    padding: 0 2;
}
"""
