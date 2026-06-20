"""Responsive ProdGuardian logo banner."""

from __future__ import annotations

from textual.widgets import Static

from prodguardian.tui.logo_art import FULL_LOGO, logo_for_terminal, logo_line_count
from prodguardian.tui.responsive import layout_mode


class LogoBanner(Static):
    """Shows full or compact logo based on terminal size."""

    DEFAULT_CSS = """
    LogoBanner {
        width: 100%;
        height: auto;
        background: $panel;
        color: $foreground;
        border: solid $primary;
        padding: 0;
        margin: 0;
        box-sizing: border-box;
        content-align: center middle;
        text-align: center;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(FULL_LOGO, markup=False, shrink=False, **kwargs)

    def on_mount(self) -> None:
        self.refresh_logo()

    def refresh_logo(self) -> None:
        size = self.app.size
        mode = layout_mode(size)
        text = logo_for_terminal(size.width, size.height, mode)
        lines = logo_line_count(text)
        self.styles.height = lines
        self.styles.min_height = lines
        self.styles.max_height = lines
        self.update(text)