"""Settings — AI provider, presets, rules, and scan tuning."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Switch, TabbedContent, TabPane

from prodguardian import __version__
from prodguardian.tui.settings_store import (
    CONFIG_PATH,
    PRESETS_RULES_PATH,
    apply_app_settings,
    clear_llm_cache,
    get_presets,
    get_rules,
    get_settings,
)
from prodguardian.tui.responsive import apply_layout_mode
from prodguardian.tui.styles import GLOBAL_CSS, MODAL_CSS
from prodguardian.tui.widgets.llm_panel import LLMProviderPanel
from prodguardian.tui.widgets.preset_editor import PresetEditor
from prodguardian.tui.widgets.rule_editor import RuleEditor
from prodguardian.tui.widgets.scan_mode_panel import ScanModePanel


class SettingsScreen(ModalScreen):
    """Presets + rules for vibe-coded production checks, plus scan/budget tuning."""

    CSS = (
        GLOBAL_CSS
        + MODAL_CSS
        + """
    SettingsScreen {
        align: center middle;
        padding: 0 1;
    }
    #settings-dialog {
        width: 98%;
        height: 98%;
        min-width: 78;
        min-height: 28;
        max-height: 98%;
        padding: 1;
        layout: vertical;
    }
    #settings-header {
        height: auto;
        margin-bottom: 1;
    }
    #settings-title {
        text-style: bold;
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-primary;
    }
    #settings-hint {
        width: 100%;
        height: auto;
        max-height: 2;
        text-align: center;
        color: $foreground-muted;
        margin-top: 1;
    }
    #settings-body {
        height: 1fr;
        min-height: 14;
        width: 100%;
        layout: vertical;
    }
    #settings-tabs {
        height: 100%;
        width: 100%;
        layout: vertical;
        border: solid $accent;
        background: $surface;
        padding: 0;
    }
    #settings-tabs > ContentTabs {
        width: 100%;
        height: 3;
        min-height: 3;
        dock: top;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $accent;
    }
    #settings-tabs Tab {
        height: 2;
        min-height: 2;
        min-width: 10;
        padding: 0 1;
    }
    #settings-tabs ContentSwitcher {
        width: 100%;
        height: 1fr;
        min-height: 10;
        border: none;
        background: transparent;
        padding: 0;
    }
    #settings-tabs TabPane {
        width: 100%;
        height: 100%;
        padding: 0;
        margin: 0;
        color: $foreground;
    }
    #settings-tabs .tab-panel {
        width: 100%;
        height: 100%;
        padding: 1;
        layout: vertical;
    }
    #settings-tabs .tab-panel-scroll {
        width: 100%;
        height: 100%;
        padding: 0;
        border: none;
        background: transparent;
    }
    #settings-tabs PresetEditor,
    #settings-tabs RuleEditor {
        width: 100%;
        height: 100%;
    }
    #settings-tabs ScanModePanel,
    #settings-tabs LLMProviderPanel {
        width: 100%;
        height: auto;
    }
    .section-title {
        text-style: bold;
        color: $text-accent;
        margin-bottom: 1;
    }
    .field-group {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        width: 100%;
        align: left middle;
    }
    #settings-tabs .field-label {
        width: 20;
        min-width: 20;
        max-width: 20;
        text-style: bold;
        color: $foreground;
        content-align: left middle;
    }
    #settings-tabs .field-group Input,
    #settings-tabs .field-group Select {
        width: 1fr;
    }
    #settings-tabs #api-panel,
    #settings-tabs #ollama-panel,
    #settings-tabs #mono-panel,
    #settings-tabs #hybrid-panel {
        width: 100%;
        margin: 0 0 1 0;
        box-sizing: border-box;
    }
    .field-hint {
        color: $foreground-muted;
        margin: 0 0 1 0;
        width: 100%;
    }
    Input {
        width: 1fr;
    }
    Switch {
        margin-bottom: 1;
    }
    #settings-footer {
        height: auto;
        width: 100%;
        margin-top: 1;
    }
    #buttons {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 3;
        align: center middle;
        padding: 0;
        margin: 0;
    }
    #settings-footer Button {
        margin: 0 1;
        height: 3;
        min-height: 3;
        max-height: 3;
    }
    #status-msg {
        width: 100%;
        height: auto;
        min-height: 0;
        max-height: 2;
        text-align: center;
        margin: 0 0 1 0;
        color: $foreground;
    }
    .layout-compact #settings-hint {
        display: none;
    }
    .layout-compact #settings-header {
        margin-bottom: 0;
    }
    """
    )

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def on_mount(self) -> None:
        apply_layout_mode(self, self.app.size)
        try:
            self.query_one("#llm-panel", LLMProviderPanel).load_ollama_models()
        except Exception:
            pass

    def on_resize(self, event) -> None:
        apply_layout_mode(self, event.size)

    def compose(self) -> ComposeResult:
        settings = get_settings()
        scan = settings["scan"]
        llm = settings["llm"]
        generator = settings["generator"]

        with Container(id="settings-dialog", classes="modal-dialog"):
            with Container(id="settings-header"):
                yield Static("ProdGuardian Settings", id="settings-title")
                yield Static(
                    "AI provider, presets & rules for production checks.",
                    id="settings-hint",
                    markup=True,
                )

            with Container(id="settings-body"):
                with TabbedContent(id="settings-tabs"):
                    with TabPane("AI Provider", id="tab-ai"):
                        with ScrollableContainer(classes="tab-panel tab-panel-scroll"):
                            yield Static(
                                "Scan mode and provider. Fix/explain use the mono model below.",
                                classes="field-hint",
                            )
                            yield ScanModePanel(
                                scan_mode=llm.get("scan_mode", "mono"),
                                analyzer_model=llm.get("analyzer_model", ""),
                                reporter_model=llm.get("reporter_model", ""),
                                id="scan-mode-panel",
                            )
                            yield LLMProviderPanel(
                                api_key=llm.get("api_key", ""),
                                model=llm.get("model", "gpt-3.5-turbo"),
                                base_url=llm.get("base_url", ""),
                                provider=llm.get("provider", "api"),
                                id="llm-panel",
                            )

                    with TabPane("Presets", id="tab-presets"):
                        with Container(classes="tab-panel"):
                            yield PresetEditor(get_presets(), id="preset-editor")

                    with TabPane("Rules", id="tab-rules"):
                        with Container(classes="tab-panel"):
                            yield RuleEditor(get_rules(), id="rule-editor")

                    with TabPane("Scan", id="tab-scan"):
                        with ScrollableContainer(classes="tab-panel tab-panel-scroll"):
                            yield Static("Scanner Options", classes="section-title")
                            yield Switch(value=scan.get("skip_test_dirs", True), id="skip-test-dirs")
                            yield Static(
                                "Skip test folders (tests/, spec/, fixtures/)",
                                classes="field-hint",
                            )
                            yield Switch(value=scan.get("parallel", True), id="parallel-scan")
                            yield Static("Scan files in parallel", classes="field-hint")
                            with Horizontal(classes="field-group"):
                                yield Label("Worker threads:", classes="field-label")
                                yield Input(
                                    value=str(scan.get("workers", 4)),
                                    id="scan-workers",
                                )
                            with Horizontal(classes="field-group"):
                                yield Label("Extra ignore dirs:", classes="field-label")
                                yield Input(
                                    value=", ".join(scan.get("ignore_dirs", [])),
                                    id="ignore-dirs",
                                )
                            with Horizontal(classes="field-group"):
                                yield Label("Groq chunk delay (s):", classes="field-label")
                                yield Input(
                                    value=str(scan.get("groq_chunk_delay", 6)),
                                    id="groq-chunk-delay",
                                )
                            yield Static(
                                "Pause between Groq AI chunks (3–20s). "
                                "Profiles: Fast=3, Balanced=6, Safe=12. "
                                "Adaptive throttle speeds up on success, slows on 429.",
                                classes="field-hint",
                            )

                    with TabPane("Budget", id="tab-budget"):
                        with ScrollableContainer(classes="tab-panel tab-panel-scroll"):
                            yield Static("AI Fix Budget", classes="section-title")
                            with Horizontal(classes="field-group"):
                                yield Label("Max cost (USD):", classes="field-label")
                                yield Input(
                                    value=str(llm.get("max_cost_usd", 0.10)),
                                    id="max-cost",
                                )
                            with Horizontal(classes="field-group"):
                                yield Label("Max tokens:", classes="field-label")
                                yield Input(
                                    value=str(llm.get("max_tokens", 32000)),
                                    id="max-tokens",
                                )

                    with TabPane("Advanced", id="tab-advanced"):
                        with ScrollableContainer(classes="tab-panel tab-panel-scroll"):
                            yield Static("Maintenance", classes="section-title")
                            yield Switch(
                                value=generator.get("auto_confirm", False),
                                id="auto-confirm",
                            )
                            yield Static(
                                "Auto-confirm generated Dockerfile / CI files",
                                classes="field-hint",
                            )
                            yield Static(f"Config: [cyan]{CONFIG_PATH}[/cyan]")
                            yield Static(f"Presets: [cyan]{PRESETS_RULES_PATH}[/cyan]")
                            yield Static(f"Version: [cyan]{__version__}[/cyan]")
                            yield Button("Clear AI Fix Cache", id="clear-cache-btn")

            with Container(id="settings-footer"):
                yield Static("", id="status-msg", markup=True)
                with Horizontal(id="buttons"):
                    yield Button("Save All", variant="primary", id="save-btn")
                    yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_all()
        elif event.button.id == "clear-cache-btn":
            removed = clear_llm_cache()
            self.query_one("#status-msg", Static).update(
                f"[green]Cleared {removed} cached fix(es).[/green]"
            )
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def _save_all(self) -> None:
        presets = self.query_one("#preset-editor", PresetEditor).collect()
        rules = self.query_one("#rule-editor", RuleEditor).collect()

        if not presets:
            self.query_one("#status-msg", Static).update(
                "[red]Add at least one preset with keywords.[/red]"
            )
            return
        if not rules:
            self.query_one("#status-msg", Static).update(
                "[red]Add at least one rule describing what to check.[/red]"
            )
            return

        workers_raw = self.query_one("#scan-workers", Input).value.strip() or "4"
        try:
            workers = max(1, min(16, int(workers_raw)))
        except ValueError:
            self.query_one("#status-msg", Static).update("[red]Workers must be 1–16.[/red]")
            return

        ignore_raw = self.query_one("#ignore-dirs", Input).value.strip()
        ignore_dirs = [part.strip() for part in ignore_raw.split(",") if part.strip()]

        from prodguardian.llm.budget import GROQ_CHUNK_THROTTLE_MAX, GROQ_CHUNK_THROTTLE_MIN

        groq_delay_raw = (
            self.query_one("#groq-chunk-delay", Input).value.strip() or "6"
        )
        try:
            groq_chunk_delay = int(groq_delay_raw)
            if not GROQ_CHUNK_THROTTLE_MIN <= groq_chunk_delay <= GROQ_CHUNK_THROTTLE_MAX:
                self.query_one("#status-msg", Static).update(
                    f"[red]Groq chunk delay must be {GROQ_CHUNK_THROTTLE_MIN}–"
                    f"{GROQ_CHUNK_THROTTLE_MAX} seconds.[/red]"
                )
                return
        except ValueError:
            self.query_one("#status-msg", Static).update(
                "[red]Groq chunk delay must be a whole number of seconds.[/red]"
            )
            return

        try:
            max_cost = float(self.query_one("#max-cost", Input).value.strip() or "0.10")
            max_tokens = int(self.query_one("#max-tokens", Input).value.strip() or "32000")
        except ValueError:
            self.query_one("#status-msg", Static).update("[red]Budget fields must be numbers.[/red]")
            return

        mode_panel = self.query_one("#scan-mode-panel", ScanModePanel)
        mode_error = mode_panel.validate()
        if mode_error:
            self.query_one("#status-msg", Static).update(f"[red]{mode_error}[/red]")
            return

        panel = self.query_one("#llm-panel", LLMProviderPanel)
        llm_config, llm_error = panel.get_llm_config()
        if llm_error:
            self.query_one("#status-msg", Static).update(f"[red]{llm_error}[/red]")
            return

        settings = {
            "presets": presets,
            "rules": rules,
            "llm": {
                **llm_config,
                **mode_panel.collect_settings(),
                "max_cost_usd": max_cost,
                "max_tokens": max_tokens,
            },
            "scan": {
                "skip_test_dirs": self.query_one("#skip-test-dirs", Switch).value,
                "parallel": self.query_one("#parallel-scan", Switch).value,
                "workers": workers,
                "ignore_dirs": ignore_dirs,
                "groq_chunk_delay": groq_chunk_delay,
            },
            "generator": {
                "auto_confirm": self.query_one("#auto-confirm", Switch).value,
            },
        }

        apply_app_settings(settings, self.app)
        self.query_one("#status-msg", Static).update("[green]Settings saved![/green]")
        self.dismiss()

    def action_cancel(self) -> None:
        self.dismiss()