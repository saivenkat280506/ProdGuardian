"""Full-page modal for scan and audit results."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, RichLog, Static

from prodguardian.tui.responsive import apply_layout_mode
from prodguardian.tui.styles import GLOBAL_CSS, MODAL_CSS
from prodguardian.utils.clipboard import copy_report_text, strip_rich_markup

_RESULT_ACTIONS = {
    "scan": {
        "repeat_label": "Scan Another Folder",
        "repeat_value": "repeat",
    },
    "audit": {
        "repeat_label": "Audit Another Folder",
        "repeat_value": "repeat",
    },
}


class ResultViewScreen(ModalScreen[str | None]):
    """Scrollable report view for scan or audit output.

    Dismiss values:
        None — return to home
        "repeat" — open folder picker for the same action again
    """

    CSS = (
        GLOBAL_CSS
        + MODAL_CSS
        + """
    ResultViewScreen {
        align: center middle;
        padding: 1;
    }
    #result-dialog {
        width: 98%;
        height: 96%;
        min-width: 72;
        min-height: 24;
        max-width: 160;
        max-height: 90%;
    }
    #result-title {
        text-style: bold;
        width: 100%;
        text-align: center;
        color: $text-primary;
        margin-bottom: 1;
    }
    #result-subtitle {
        width: 100%;
        text-align: center;
        color: $foreground-muted;
        margin-bottom: 1;
    }
    #result-body-wrap {
        height: 1fr;
        min-height: 12;
        border: solid $accent;
        background: $surface;
        margin-bottom: 1;
    }
    #result-body {
        height: 100%;
        width: 100%;
        padding: 1;
    }
    #result-buttons {
        width: 100%;
        height: auto;
        min-height: 3;
        align: center middle;
    }
    #result-buttons Button {
        margin: 0 1;
        min-width: 16;
    }
    .layout-compact #result-dialog {
        width: 100%;
        height: 100%;
    }
    """
    )

    BINDINGS = [
        ("escape", "back_home", "Back"),
        ("c", "copy_report", "Copy"),
        ("ctrl+c", "copy_report", "Copy"),
    ]

    def __init__(
        self,
        title: str,
        project_path: str,
        body: str,
        *,
        kind: str = "scan",
    ):
        super().__init__()
        self._title = title
        self._project_path = project_path
        self._body = body
        self._kind = kind if kind in _RESULT_ACTIONS else "scan"
        self._actions = _RESULT_ACTIONS[self._kind]

    def compose(self) -> ComposeResult:
        with Container(id="result-dialog", classes="modal-dialog"):
            yield Static(self._title, id="result-title")
            yield Static(f"Project: {self._project_path}", id="result-subtitle")
            with VerticalScroll(id="result-body-wrap"):
                yield RichLog(id="result-body", markup=True, wrap=True, auto_scroll=False)
            with Horizontal(id="result-buttons"):
                yield Button("Copy Report", variant="success", id="copy-btn")
                yield Button(
                    self._actions["repeat_label"],
                    variant="primary",
                    id="repeat-btn",
                )
                yield Button("Back to Home", variant="default", id="home-btn")

    def on_mount(self) -> None:
        apply_layout_mode(self, self.app.size)
        log = self.query_one("#result-body", RichLog)
        for paragraph in self._body.split("\n"):
            if paragraph.strip():
                log.write(paragraph)
            else:
                log.write("")

    def on_resize(self, event) -> None:
        apply_layout_mode(self, event.size)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-btn":
            self.action_copy_report()
        elif event.button.id == "repeat-btn":
            self.action_repeat()
        elif event.button.id == "home-btn":
            self.action_back_home()

    def _report_plain_text(self) -> str:
        header = f"{self._title}\nProject: {self._project_path}\n\n"
        return header + strip_rich_markup(self._body)

    def action_copy_report(self) -> None:
        text = self._report_plain_text()
        copied = copy_report_text(
            text,
            terminal_copy=self.app.copy_to_clipboard,
        )
        if copied:
            self.notify("Report copied to clipboard", title="Copied", timeout=3)
        else:
            self.notify(
                "Could not access clipboard. Select text manually or use Ctrl+Shift+C.",
                title="Copy failed",
                severity="warning",
                timeout=5,
            )

    def action_repeat(self) -> None:
        self.dismiss(self._actions["repeat_value"])

    def action_back_home(self) -> None:
        self.dismiss(None)