"""Scan-only AI setup — mode, models, and provider before picking a project."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from prodguardian.llm.llm_router import prepare_scan_models, resolve_scan_llm_settings
from prodguardian.tui.settings_store import apply_llm_config, get_saved_llm, get_settings
from prodguardian.tui.responsive import apply_layout_mode
from prodguardian.tui.styles import GLOBAL_CSS, MODAL_CSS
from prodguardian.tui.widgets.llm_panel import LLMProviderPanel
from prodguardian.tui.widgets.scan_mode_panel import ScanModePanel


class LLMConfigScreen(ModalScreen[bool]):
    """Focused pre-scan wizard — not the full settings page."""

    CSS = (
        GLOBAL_CSS
        + MODAL_CSS
        + """
    LLMConfigScreen {
        align: center middle;
        padding: 1;
    }
    #scan-dialog {
        height: auto;
        max-height: 94%;
        overflow-y: auto;
    }
    #scan-dialog.modal-dialog {
        height: auto;
    }
    #scan-title {
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        color: $text-primary;
    }
    #scan-hint {
        width: 100%;
        text-align: center;
        color: $foreground-muted;
        margin-bottom: 1;
    }
    .layout-compact #scan-hint {
        display: none;
    }
    #buttons {
        width: 100%;
        height: auto;
        min-height: 3;
        align: center middle;
        margin-top: 1;
        padding: 0;
    }
    #buttons Button {
        margin: 0 1;
        min-width: 16;
        height: 3;
    }
    #status-msg {
        width: 100%;
        text-align: center;
        margin-top: 1;
        color: $foreground;
    }
    """
    )

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, mode: str = "scan"):
        super().__init__()
        self._busy = False

    def compose(self) -> ComposeResult:
        settings = get_settings()
        llm = settings["llm"]
        saved = get_saved_llm()
        with Container(id="scan-dialog", classes="modal-dialog"):
            yield Static("Ready to Scan", id="scan-title")
            yield Static(
                "Choose Mono (one model) or Hybrid (analyzer + reporter). "
                "Ollama models download automatically when needed.",
                id="scan-hint",
            )
            yield ScanModePanel(
                scan_mode=llm.get("scan_mode", "mono"),
                analyzer_model=llm.get("analyzer_model", ""),
                reporter_model=llm.get("reporter_model", ""),
                id="scan-mode-panel",
            )
            yield LLMProviderPanel(
                api_key=saved["api_key"],
                model=saved["model"],
                base_url=saved["base_url"],
                provider=saved["provider"],
                id="llm-panel",
            )
            yield Static("", id="status-msg", markup=True)
            with Horizontal(id="buttons"):
                yield Button("Continue to Project", variant="primary", id="continue-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        apply_layout_mode(self, self.app.size)
        self.query_one("#llm-panel", LLMProviderPanel).load_ollama_models()

    def on_resize(self, event) -> None:
        apply_layout_mode(self, event.size)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._busy:
            return
        if event.button.id == "continue-btn":
            self._continue()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def _update_status(self, message: str) -> None:
        self.query_one("#status-msg", Static).update(message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.query_one("#continue-btn", Button).disabled = busy
        self.query_one("#cancel-btn", Button).disabled = busy
        self.query_one("#llm-panel", LLMProviderPanel).set_busy(busy)

    def _continue(self) -> None:
        mode_panel = self.query_one("#scan-mode-panel", ScanModePanel)
        panel = self.query_one("#llm-panel", LLMProviderPanel)

        mode_error = mode_panel.validate()
        if mode_error:
            self._update_status(f"[red]{mode_error}[/red]")
            return

        llm_config, error = panel.get_llm_config()
        if error:
            self._update_status(f"[red]{error}[/red]")
            return

        llm_config.update(mode_panel.collect_settings())
        scan_settings = resolve_scan_llm_settings({**get_settings()["llm"], **llm_config})

        self._set_busy(True)
        self._update_status("[dim]Preparing models for scan...[/dim]")
        self._prepare_and_save(llm_config, scan_settings)

    @work(thread=True, exclusive=True)
    def _prepare_and_save(self, llm_config: dict, scan_settings) -> None:
        def on_status(message: str) -> None:
            self.app.call_from_thread(self._update_status, f"[dim]{message}[/dim]")

        error = prepare_scan_models(scan_settings, on_progress=on_status)
        if error:
            self.app.call_from_thread(self._on_error, error)
            return
        self.app.call_from_thread(self._finish_save, llm_config)

    def _finish_save(self, llm_config: dict) -> None:
        apply_llm_config(llm_config, self.app)
        mode = llm_config.get("scan_mode", "mono")
        self._update_status(
            f"[green]{mode.title()} scan configured. Opening project picker...[/green]"
        )
        self.dismiss(True)

    def _on_error(self, message: str) -> None:
        self._set_busy(False)
        self._update_status(f"[red]{message}[/red]")

    def action_cancel(self) -> None:
        if self._busy:
            return
        self.dismiss(False)