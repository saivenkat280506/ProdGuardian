#!/usr/bin/env python
"""
ProdGuardian Terminal UI - Chat interface for production readiness auditing.
"""
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, RichLog, Static

from .llm_store import get_saved_llm, is_llm_configured
from .orchestrator import Orchestrator
from .screens.project_picker import ProjectPickerScreen
from .screens.result_view import ResultViewScreen
from .screens.scan_setup import ScanSetupScreen
from .screens.settings import SettingsScreen
from .responsive import apply_layout_mode
from .styles import GLOBAL_CSS, MAIN_LAYOUT_CSS
from .widgets.logo_banner import LogoBanner
from .widgets.scan_progress import OperationProgressPanel


class ChatLog(RichLog):
    """Custom chat log with auto-scroll."""
    pass


class StatusBar(Static):
    """Shows current project, API key status, and model."""

    def on_mount(self):
        self.update_status()

    def update_status(
        self,
        project_path: Path | None = None,
        operation: str | None = None,
    ):
        llm = get_saved_llm()
        model = llm.get("model", "not set")
        if llm.get("provider") == "ollama":
            key_status = "ollama"
        elif llm.get("api_key"):
            key_status = "set"
        else:
            key_status = "not set (Settings)"
        if project_path:
            project_status = str(project_path)
        else:
            project_status = "none (click Scan)"
        if operation == "scan":
            op_status = "[bold cyan]● SCANNING[/bold cyan]"
        elif operation == "audit":
            op_status = "[bold yellow]● AUDITING[/bold yellow]"
        else:
            op_status = None

        if op_status:
            self.update(
                f"{op_status} | Project: {project_status} | "
                f"Model: {model} | API Key: {key_status}"
            )
        else:
            self.update(
                f"Project: {project_status} | Model: {model} | API Key: {key_status}"
            )


class ProdGuardianTUI(App):
    CSS = (
        GLOBAL_CSS
        + MAIN_LAYOUT_CSS
        + """
    Screen {
        layout: vertical;
        background: $background;
    }
    Header, Footer {
        width: 100%;
        padding: 0 1;
        box-sizing: border-box;
    }
    #main-column {
        width: 100%;
        height: 1fr;
        padding: 0 1;
        margin: 0;
        box-sizing: border-box;
        overflow: hidden;
    }
    #logo {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        box-sizing: border-box;
    }
    #chat-container {
        width: 100%;
        height: 1fr;
        min-height: 8;
        margin: 0 0 1 0;
        border: solid $accent;
        padding: 0;
        box-sizing: border-box;
    }
    #chat-log {
        height: 100%;
        width: 100%;
        background: $surface;
        color: $foreground;
        padding: 1;
        box-sizing: border-box;
    }
    #bottom-panel {
        width: 100%;
        height: auto;
        layout: vertical;
        margin: 0;
        padding: 0;
        box-sizing: border-box;
        overflow: hidden;
    }
    OperationProgressPanel {
        width: 100%;
        margin: 0 0 1 0;
        box-sizing: border-box;
    }
    #scan-btn.scanning {
        background: $warning;
        color: $text;
    }
    #actions {
        width: 100%;
        height: auto;
        min-height: 3;
        align: left middle;
        margin: 0 0 1 0;
        padding: 0;
        box-sizing: border-box;
    }
    #actions Button {
        margin-right: 1;
        width: auto;
        min-width: 16;
    }
    #status-bar {
        width: 100%;
        height: auto;
        min-height: 1;
        max-height: 3;
        background: $panel;
        color: $foreground;
        padding: 0 1;
        margin: 0;
        overflow-x: auto;
        overflow-y: hidden;
        box-sizing: border-box;
    }
    """
    )

    BINDINGS = [
        Binding("ctrl+s", "scan_project", "Scan"),
        Binding("ctrl+comma", "open_settings", "Settings"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-column"):
            yield LogoBanner(id="logo")
            with Container(id="chat-container"):
                yield ChatLog(id="chat-log", markup=True, wrap=True, auto_scroll=True)
            with Vertical(id="bottom-panel"):
                yield OperationProgressPanel(id="scan-progress", classes="hidden")
                with Horizontal(id="actions"):
                    yield Button("Scan", variant="primary", id="scan-btn")
                    yield Button("Audit", variant="default", id="audit-btn")
                yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self):
        self.theme = "textual-dark"
        self._active_operation: str | None = None
        apply_layout_mode(self, self.size)
        try:
            self.query_one("#logo", LogoBanner).refresh_logo()
        except Exception:
            pass
        self.orchestrator = Orchestrator()
        self.project_path = None
        chat = self.query_one("#chat-log")
        chat.write("[bold green]ProdGuardian ready![/bold green]")
        chat.write(
            "Click [cyan]Scan[/cyan] or [cyan]Audit[/cyan] — results open in a dedicated report page."
        )
        chat.write("[bold]Ctrl+S[/] Scan · [bold]Ctrl+,[/] Settings\n")
        self._update_status_bar()

    def on_resize(self, event) -> None:
        apply_layout_mode(self, event.size)
        try:
            self.query_one("#logo", LogoBanner).refresh_logo()
        except Exception:
            pass

    def action_open_settings(self):
        self.push_screen(SettingsScreen())

    def action_scan_project(self):
        self._begin_scan_flow()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "scan-btn":
            self._begin_scan_flow()
        elif event.button.id == "audit-btn":
            self._begin_project_action("audit")

    def _show_result_page(self, kind: str, project_path: Path, body: str) -> None:
        title = "Scan Results" if kind == "scan" else "Audit Results"

        def on_result_closed(action: str | None) -> None:
            if action == "repeat":
                if kind == "scan":
                    self._begin_scan_flow()
                else:
                    self._begin_project_action("audit")

        self.push_screen(
            ResultViewScreen(
                title,
                str(project_path),
                body,
                kind=kind,
            ),
            on_result_closed,
        )

    def _begin_scan_flow(self):
        if is_llm_configured():
            self._begin_project_action("scan")
            return
        self.push_screen(
            ScanSetupScreen(),
            lambda configured: self._on_scan_setup_done(configured),
        )

    def _on_scan_setup_done(self, configured: bool):
        chat = self.query_one("#chat-log")
        if not configured:
            chat.write("[dim]Scan setup cancelled.[/dim]")
            return
        self._begin_project_action("scan")

    def _begin_project_action(self, action: str):
        start_path = self.project_path or Path.cwd()
        self.push_screen(
            ProjectPickerScreen(start_path=start_path, action=action),
            lambda path: self._on_project_selected(path, action),
        )

    @work(exclusive=True)
    async def _on_project_selected(self, path: Path | None, action: str):
        chat = self.query_one("#chat-log")
        if path is None:
            chat.write("[dim]Returned to home.[/dim]")
            return

        self.project_path = path
        self.orchestrator.set_project(path)
        self._update_status_bar()

        try:
            if action == "scan":
                chat.write(f"[bold cyan]Scanning {path}...[/bold cyan]")
                self._start_operation_progress("scan", path)
                response = await self.orchestrator._run_scan(
                    on_progress=self._make_progress_cb()
                )
                self._show_result_page("scan", path, response)
                chat.write("[green]Scan complete.[/green] See report above.")
            else:
                chat.write(f"[bold yellow]Auditing {path}...[/bold yellow]")
                self._start_operation_progress("audit", path)
                response = await self.orchestrator._run_audit(
                    on_progress=self._make_progress_cb()
                )
                self._show_result_page("audit", path, response)
                chat.write("[green]Audit complete.[/green] See report above.")
        except Exception as exc:
            chat.write(f"[red]Operation failed: {exc}[/red]")
            raise
        finally:
            self._finish_operation_progress()

    def _update_status_bar(self, operation: str | None = None):
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_status(self.project_path, operation=operation)
        except Exception:
            pass

    def _set_operation_ui(self, operation: str | None) -> None:
        self._active_operation = operation
        if operation:
            self.add_class("operation-active")
        else:
            self.remove_class("operation-active")

        try:
            scan_btn = self.query_one("#scan-btn", Button)
            audit_btn = self.query_one("#audit-btn", Button)
            busy = operation is not None
            scan_btn.disabled = busy
            audit_btn.disabled = busy
            scan_btn.remove_class("scanning")
            audit_btn.remove_class("auditing")
            if operation == "scan":
                scan_btn.label = "Scanning..."
                scan_btn.add_class("scanning")
            elif operation == "audit":
                audit_btn.label = "Auditing..."
                audit_btn.add_class("auditing")
            else:
                scan_btn.label = "Scan"
                audit_btn.label = "Audit"
        except Exception:
            pass
        self._update_status_bar(operation=operation)

    def _make_progress_cb(self):
        def callback(stage: str, data: dict) -> None:
            self.call_from_thread(self._on_operation_progress, stage, data)

        return callback

    def _on_operation_progress(self, stage: str, data: dict) -> None:
        try:
            panel = self.query_one("#scan-progress", OperationProgressPanel)
            panel.update_from_event(stage, data)
        except Exception:
            pass

    def _start_operation_progress(
        self,
        operation: str,
        project_path: Path | None = None,
    ) -> None:
        self._set_operation_ui(operation)
        try:
            panel = self.query_one("#scan-progress", OperationProgressPanel)
            panel.show(operation)
            verb = "scan" if operation == "scan" else "audit"
            panel.update_from_event(
                "init",
                {
                    "message": (
                        f"Starting {verb} of "
                        f"{project_path or self.project_path or Path.cwd()}"
                    ),
                },
            )
        except Exception:
            pass

    def _finish_operation_progress(self) -> None:
        try:
            panel = self.query_one("#scan-progress", OperationProgressPanel)
            op = self._active_operation or "scan"
            label = "Scan complete" if op == "scan" else "Audit complete"
            panel.update_from_event("done", {"message": label})
            panel.hide()
        except Exception:
            pass
        self._set_operation_ui(None)


def run():
    app = ProdGuardianTUI()
    app.run()


if __name__ == "__main__":
    run()