"""Scan mode picker — Mono (one model) or Hybrid (analyzer + reporter)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Label, RadioButton, RadioSet, Select, Static

from prodguardian.llm.llm_router import (
    HYBRID_RECOMMENDED_PAIRS,
    SCAN_MODE_HYBRID,
    SCAN_MODE_MONO,
)
from prodguardian.tui.styles import GLOBAL_CSS


class ScanModePanel(Widget):
    """Let users choose Mono vs Hybrid scan models before a scan."""

    DEFAULT_CSS = (
        GLOBAL_CSS
        + """
    ScanModePanel {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        color: $foreground;
    }
    #scan-mode-choice {
        width: 100%;
        margin-bottom: 1;
    }
    #mono-panel, #hybrid-panel {
        width: 100%;
        border: tall $accent;
        padding: 1;
        margin-bottom: 1;
        height: auto;
        background: $panel;
    }
    #mono-panel.hidden, #hybrid-panel.hidden {
        display: none;
    }
    .field-group {
        width: 100%;
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        align: left middle;
    }
    .field-label {
        width: 20;
        min-width: 20;
        max-width: 20;
        text-style: bold;
        color: $foreground;
        content-align: left middle;
    }
    Input, Select {
        width: 1fr;
    }
    .section-title {
        text-style: bold;
        color: $text-accent;
        width: 100%;
        margin-bottom: 1;
    }
    .mode-hint {
        color: $foreground-muted;
        margin-bottom: 1;
        width: 100%;
    }
    """
    )

    def __init__(
        self,
        scan_mode: str = SCAN_MODE_MONO,
        analyzer_model: str = "",
        reporter_model: str = "",
        *,
        id: str | None = None,
    ):
        super().__init__(id=id)
        self._scan_mode = scan_mode if scan_mode in (SCAN_MODE_MONO, SCAN_MODE_HYBRID) else SCAN_MODE_MONO
        self._analyzer_model = analyzer_model
        self._reporter_model = reporter_model

    def compose(self) -> ComposeResult:
        yield Static("Scan Mode", classes="section-title")
        with RadioSet(id="scan-mode-choice"):
            yield RadioButton(
                "Mono — one model for the whole scan (default)",
                id="mode-mono",
                value=self._scan_mode == SCAN_MODE_MONO,
            )
            yield RadioButton(
                "Hybrid — large analyzer + fast reporter (advanced)",
                id="mode-hybrid",
                value=self._scan_mode == SCAN_MODE_HYBRID,
            )

        with Vertical(id="mono-panel"):
            yield Static(
                "Mono uses the AI provider below. Enter any LiteLLM model string, "
                "e.g. groq/llama-3.3-70b-versatile or ollama/llama3.2:3b.",
                classes="mode-hint",
            )

        with Vertical(id="hybrid-panel", classes="hidden"):
            yield Static(
                "Analyzer reads chunks; reporter writes final JSON findings. "
                "Recommended pairs:",
                classes="mode-hint",
            )
            pair_options = [(p["label"], p["label"]) for p in HYBRID_RECOMMENDED_PAIRS]
            yield Select(
                pair_options,
                prompt="Choose a recommended pair",
                id="hybrid-pair-select",
                allow_blank=True,
            )
            with Horizontal(classes="field-group"):
                yield Label("Analyzer model:", classes="field-label")
                yield Input(
                    placeholder="groq/llama-3.3-70b-versatile",
                    value=self._analyzer_model,
                    id="analyzer-model",
                )
            with Horizontal(classes="field-group"):
                yield Label("Reporter model:", classes="field-label")
                yield Input(
                    placeholder="groq/llama-3.1-8b-instant",
                    value=self._reporter_model,
                    id="reporter-model",
                )

    def on_mount(self) -> None:
        self._sync_mode_panels()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._sync_mode_panels()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "hybrid-pair-select" or not event.value:
            return
        for pair in HYBRID_RECOMMENDED_PAIRS:
            if pair["label"] == event.value:
                self.query_one("#analyzer-model", Input).value = pair["analyzer"]
                self.query_one("#reporter-model", Input).value = pair["reporter"]
                break

    def _sync_mode_panels(self) -> None:
        hybrid = self.query_one("#mode-hybrid", RadioButton).value
        self.query_one("#mono-panel", Vertical).set_class(hybrid, "hidden")
        self.query_one("#hybrid-panel", Vertical).set_class(not hybrid, "hidden")

    def get_scan_mode(self) -> str:
        if self.query_one("#mode-hybrid", RadioButton).value:
            return SCAN_MODE_HYBRID
        return SCAN_MODE_MONO

    def get_hybrid_models(self) -> tuple[str, str]:
        analyzer = self.query_one("#analyzer-model", Input).value.strip()
        reporter = self.query_one("#reporter-model", Input).value.strip()
        return analyzer, reporter

    def validate(self) -> str | None:
        if self.get_scan_mode() != SCAN_MODE_HYBRID:
            return None
        analyzer, reporter = self.get_hybrid_models()
        if not analyzer:
            return "Enter an analyzer model for hybrid scan."
        if not reporter:
            return "Enter a reporter model for hybrid scan."
        return None

    def collect_settings(self) -> dict[str, str]:
        mode = self.get_scan_mode()
        payload: dict[str, str] = {"scan_mode": mode}
        if mode == SCAN_MODE_HYBRID:
            analyzer, reporter = self.get_hybrid_models()
            payload["analyzer_model"] = analyzer
            payload["reporter_model"] = reporter
        return payload