"""Reusable AI provider panel for settings and scan flows."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select, Static

from prodguardian.llm.ollama import (
    DEFAULT_OLLAMA_HOST,
    build_ollama_select_options,
    ensure_ollama_running,
    is_model_installed,
    list_ollama_models,
    ollama_litellm_model,
    pull_ollama_model,
)
from prodguardian.tui.settings_store import get_saved_llm
from prodguardian.tui.styles import GLOBAL_CSS


class LLMProviderPanel(Widget):
    """Cloud API or Ollama model picker."""

    DEFAULT_CSS = (
        GLOBAL_CSS
        + """
    LLMProviderPanel {
        width: 100%;
        height: auto;
        color: $foreground;
    }
    #provider-choice {
        width: 100%;
        margin-bottom: 1;
    }
    #api-panel, #ollama-panel {
        width: 100%;
        border: tall $accent;
        padding: 1;
        margin-bottom: 1;
        height: auto;
        background: $panel;
        color: $foreground;
    }
    #api-panel.hidden, #ollama-panel.hidden {
        display: none;
    }
    .field-group {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        width: 100%;
        align: left middle;
    }
    .field-label {
        width: 1fr;
        max-width: 16;
        min-width: 10;
        text-style: bold;
        color: $foreground;
        content-align: left middle;
    }
    Input, Select {
        width: 2fr;
        min-width: 20;
    }
    """
    )

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-3.5-turbo",
        base_url: str = "",
        provider: str = "api",
        *,
        id: str | None = None,
    ):
        super().__init__(id=id)
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._provider = provider
        self._installed_models: list[str] = []
        self._busy = False

    def compose(self) -> ComposeResult:
        with RadioSet(id="provider-choice"):
            yield RadioButton("Cloud API", id="provider-api", value=self._provider != "ollama")
            yield RadioButton("Ollama (local)", id="provider-ollama", value=self._provider == "ollama")

        with Vertical(id="api-panel"):
            with Horizontal(classes="field-group"):
                yield Label("API Key:", classes="field-label")
                yield Input(
                    placeholder="sk-..., gsk_..., etc.",
                    value=self._api_key,
                    password=True,
                    id="api-key",
                )
            with Horizontal(classes="field-group"):
                yield Label("Model:", classes="field-label")
                yield Input(
                    placeholder="gpt-3.5-turbo, groq/llama3, etc.",
                    value=self._model if not self._model.startswith("ollama/") else "gpt-3.5-turbo",
                    id="model",
                )
            with Horizontal(classes="field-group"):
                yield Label("Base URL:", classes="field-label")
                yield Input(
                    placeholder="Optional (OpenRouter, proxies, etc.)",
                    value=self._base_url if not self._model.startswith("ollama/") else "",
                    id="base-url",
                )

        with Vertical(id="ollama-panel", classes="hidden"):
            yield Static("Installed = [installed]. Small models = download on scan.")
            yield Select(
                [("Loading models...", "")],
                prompt="Choose an Ollama model",
                id="ollama-model-select",
                allow_blank=False,
            )
            yield Button("Refresh Models", id="refresh-ollama-btn")

    def on_mount(self) -> None:
        self._sync_provider_panels()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._sync_provider_panels()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-ollama-btn" and not self._busy:
            self.load_ollama_models()

    def _sync_provider_panels(self) -> None:
        use_ollama = self.query_one("#provider-ollama", RadioButton).value
        self.query_one("#api-panel", Vertical).set_class(use_ollama, "hidden")
        self.query_one("#ollama-panel", Vertical).set_class(not use_ollama, "hidden")

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.query_one("#refresh-ollama-btn", Button).disabled = busy
        self.query_one("#ollama-model-select", Select).disabled = busy

    @work(thread=True)
    def load_ollama_models(self) -> None:
        models, error = list_ollama_models()
        self.app.call_from_thread(self._show_ollama_models, models, error)

    def _show_ollama_models(self, models: list[str], error: str | None) -> None:
        select = self.query_one("#ollama-model-select", Select)
        self._installed_models = models
        options = build_ollama_select_options(models)
        if options:
            select.set_options(options)

        saved = get_saved_llm()
        saved_ollama = (
            saved["model"].removeprefix("ollama/")
            if saved["model"].startswith("ollama/")
            else ""
        )
        if saved_ollama:
            for _display, value in options:
                if value == saved_ollama or is_model_installed(saved_ollama, [value]):
                    select.value = value
                    break

    def get_llm_config(self) -> tuple[dict[str, str] | None, str | None]:
        use_ollama = self.query_one("#provider-ollama", RadioButton).value

        if use_ollama:
            selected = self.query_one("#ollama-model-select", Select).value
            if not selected:
                return None, "Choose an Ollama model from the dropdown."
            return {
                "provider": "ollama",
                "model": ollama_litellm_model(str(selected)),
                "base_url": DEFAULT_OLLAMA_HOST,
                "api_key": "ollama",
            }, None

        api_key = self.query_one("#api-key", Input).value.strip()
        model = self.query_one("#model", Input).value.strip() or "gpt-3.5-turbo"
        base_url = self.query_one("#base-url", Input).value.strip()

        if not api_key:
            return None, "Enter an API key or switch to Ollama."

        config: dict[str, str] = {"provider": "api", "model": model, "api_key": api_key}
        if base_url:
            config["base_url"] = base_url
        return config, None

    @work(thread=True, exclusive=True)
    def prepare_ollama_for_scan(
        self,
        model_name: str,
        llm_config: dict[str, str],
        on_status,
        on_success,
        on_error,
    ) -> None:
        def report(message: str) -> None:
            self.app.call_from_thread(on_status, message)

        report("Starting Ollama server...")
        start_error = ensure_ollama_running()
        if start_error:
            self.app.call_from_thread(on_error, start_error)
            return

        installed, _ = list_ollama_models()
        self.app.call_from_thread(self._show_ollama_models, installed, None)

        if not is_model_installed(model_name, installed):
            report(f"Downloading {model_name}... This may take a few minutes.")

            def on_pull_progress(line: str) -> None:
                self.app.call_from_thread(on_status, line)

            pull_error = pull_ollama_model(model_name, on_progress=on_pull_progress)
            if pull_error:
                self.app.call_from_thread(on_error, pull_error)
                return

        self.app.call_from_thread(on_success, llm_config, model_name)