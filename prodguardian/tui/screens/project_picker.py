from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static

from prodguardian.tui.responsive import apply_layout_mode
from prodguardian.tui.styles import GLOBAL_CSS, MODAL_CSS


_PICKER_COPY = {
    "scan": {
        "title": "Open Project to Scan",
        "hint": (
            "Pick your app folder. ProdGuardian will AI-scan it for leaks "
            "that must not ship to production."
        ),
        "confirm": "Scan Project",
    },
    "audit": {
        "title": "Open Project to Audit",
        "hint": (
            "Pick your app folder. ProdGuardian will check for missing "
            "production assets (Dockerfile, CI, env files, and more)."
        ),
        "confirm": "Audit Project",
    },
}


class ProjectPickerScreen(ModalScreen[Path | None]):
    """Ask the user which project directory to open before scanning or auditing."""

    CSS = (
        GLOBAL_CSS
        + MODAL_CSS
        + """
    ProjectPickerScreen {
        align: center middle;
        padding: 1;
    }
    #picker-dialog {
        width: 98%;
        height: 96%;
        min-width: 78;
        min-height: 28;
        max-width: 150;
        max-height: 68;
        layout: vertical;
        border: solid $primary;
        background: $surface;
        color: $foreground;
        padding: 1 2;
    }
    #picker-title {
        text-style: bold;
        width: 100%;
        height: auto;
        text-align: center;
        color: $text-primary;
        margin-bottom: 1;
    }
    #picker-hint {
        width: 100%;
        height: auto;
        text-align: center;
        color: $foreground-muted;
        margin-bottom: 1;
    }
    #picker-body {
        height: 1fr;
        min-height: 14;
        layout: vertical;
        width: 100%;
    }
    #project-tree {
        height: 1fr;
        min-height: 12;
        width: 100%;
        border: solid $accent;
        margin-bottom: 1;
        background: $surface;
        color: $foreground;
    }
    .field-group {
        width: 100%;
        height: auto;
        min-height: 3;
        margin-bottom: 1;
    }
    .field-label {
        width: 16;
        min-width: 12;
        text-style: bold;
        color: $foreground;
        content-align: left middle;
    }
    #project-path {
        width: 1fr;
        min-width: 20;
    }
    #status-msg {
        width: 100%;
        height: auto;
        min-height: 1;
        text-align: center;
        color: $foreground;
        margin-bottom: 1;
    }
    #buttons {
        width: 100%;
        height: auto;
        min-height: 3;
        align: center middle;
        padding: 0;
    }
    #buttons Button {
        margin: 0 1;
        min-width: 18;
        height: 3;
    }

    /* Compact terminal */
    .layout-compact #picker-dialog {
        width: 100%;
        height: 100%;
        min-height: 22;
        padding: 1;
    }
    .layout-compact #picker-hint {
        display: none;
    }
    .layout-compact .field-group {
        layout: vertical;
        height: auto;
    }
    .layout-compact .field-label {
        width: 100%;
        margin-bottom: 1;
    }
    .layout-compact #project-tree {
        min-height: 8;
    }

    /* Large terminal */
    .layout-expanded #picker-dialog {
        width: 90%;
        height: 90%;
        max-width: 170;
        max-height: 76;
    }
    .layout-expanded #project-tree {
        min-height: 20;
    }
    """
    )

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def __init__(self, start_path: Path | None = None, action: str = "scan"):
        super().__init__()
        self._start_path = start_path or Path.home()
        self._action = action if action in _PICKER_COPY else "scan"
        self._copy = _PICKER_COPY[self._action]

    def compose(self) -> ComposeResult:
        with Container(id="picker-dialog"):
            yield Static(self._copy["title"], id="picker-title")
            yield Static(self._copy["hint"], id="picker-hint")
            with Container(id="picker-body"):
                yield DirectoryTree(str(self._start_path), id="project-tree")
                with Horizontal(classes="field-group"):
                    yield Label("Project path:", classes="field-label")
                    yield Input(
                        placeholder="C:\\Users\\you\\my-app",
                        value=str(self._start_path),
                        id="project-path",
                    )
            yield Static("", id="status-msg", markup=True)
            with Horizontal(id="buttons"):
                yield Button(
                    self._copy["confirm"],
                    variant="primary",
                    id="confirm-btn",
                )
                yield Button("Back", variant="default", id="back-btn")

    def on_mount(self) -> None:
        apply_layout_mode(self, self.app.size)

    def on_resize(self, event) -> None:
        apply_layout_mode(self, event.size)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self.query_one("#project-path", Input).value = str(event.path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            self._confirm_project()
        elif event.button.id == "back-btn":
            self.action_back()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "project-path":
            self._confirm_project()

    def _confirm_project(self) -> None:
        raw = self.query_one("#project-path", Input).value.strip().strip('"')
        if not raw:
            self.query_one("#status-msg", Static).update("[red]Enter a project path.[/red]")
            return

        path = Path(raw).expanduser().resolve()
        if not path.exists():
            self.query_one("#status-msg", Static).update(f"[red]Path not found: {path}[/red]")
            return
        if not path.is_dir():
            self.query_one("#status-msg", Static).update("[red]Path must be a directory.[/red]")
            return

        self.dismiss(path)

    def action_back(self) -> None:
        self.dismiss(None)