"""Live scan/audit progress panel for the TUI."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import LoadingIndicator, ProgressBar, Static

from prodguardian.scan.progress import OPERATION_STAGES

_SPINNER_FRAMES = "|/-\\"

_OPERATION_TITLES = {
    "scan": {
        "active": "[bold cyan]Scanning in progress...[/bold cyan]",
        "done": "[bold green]Scan complete[/bold green]",
    },
    "audit": {
        "active": "[bold yellow]Audit in progress...[/bold yellow]",
        "done": "[bold green]Audit complete[/bold green]",
    },
}


class OperationProgressPanel(Widget):
    """Shows staged scan or audit progress with live updates."""

    DEFAULT_CSS = """
    OperationProgressPanel {
        layout: vertical;
        width: 100%;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1;
        box-sizing: border-box;
    }
    OperationProgressPanel.scanning {
        border: solid $accent;
        background: $panel;
    }
    OperationProgressPanel.auditing {
        border: solid $warning;
        background: $panel;
    }
    OperationProgressPanel.hidden {
        display: none;
        height: 0;
        max-height: 0;
        padding: 0;
        border: none;
        margin: 0;
    }
    OperationProgressPanel #progress-header {
        layout: horizontal;
        height: 1;
        width: 100%;
        align: left middle;
    }
    OperationProgressPanel #progress-spinner {
        width: 4;
        height: 1;
        margin-right: 1;
        background: transparent;
    }
    OperationProgressPanel #progress-title {
        text-style: bold;
        color: $text-accent;
        height: 1;
        width: 1fr;
    }
    OperationProgressPanel #progress-bar {
        width: 100%;
        height: 1;
        margin-top: 1;
    }
    OperationProgressPanel #progress-current {
        height: 1;
        width: 100%;
        color: $foreground;
        margin-top: 1;
        display: none;
    }
    OperationProgressPanel #progress-stages-scroll {
        height: 4;
        width: 100%;
        margin-top: 1;
        scrollbar-size: 1 1;
    }
    OperationProgressPanel #progress-stages {
        width: 100%;
        height: auto;
        color: $foreground;
    }
    OperationProgressPanel #progress-detail {
        height: 1;
        width: 100%;
        color: $foreground-muted;
        margin-top: 1;
        text-overflow: ellipsis;
    }
    OperationProgressPanel #progress-note {
        height: auto;
        max-height: 2;
        width: 100%;
        color: $foreground-muted;
        margin-top: 1;
        overflow-y: auto;
    }
    OperationProgressPanel.mode-audit #progress-note {
        display: none;
    }
    """

    def __init__(
        self,
        *,
        operation: str = "scan",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._operation = operation if operation in OPERATION_STAGES else "scan"
        self._stages = OPERATION_STAGES[self._operation]
        self._stage_order = [sid for sid, _ in self._stages]
        self._completed: set[str] = set()
        self._active_stage = "init"
        self._current_message = ""
        self._detail_text = ""
        self._note = ""
        self._frame_idx = 0
        self._stage_started_at = time.monotonic()
        self._files_total: int | None = None
        self._files_done: int | None = None
        self._chunks_total: int | None = None
        self._chunks_done: int | None = None
        self._spinner_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="progress-header"):
                yield LoadingIndicator(id="progress-spinner")
                yield Static("Working...", id="progress-title", markup=True)
            yield ProgressBar(id="progress-bar", show_eta=False)
            yield Static("", id="progress-current", markup=True)
            with VerticalScroll(id="progress-stages-scroll", can_focus=True):
                yield Static("", id="progress-stages", markup=True)
            yield Static("", id="progress-detail", markup=True)
            yield Static("", id="progress-note", markup=True)

    def on_mount(self) -> None:
        self.add_class(f"mode-{self._operation}")

    def set_operation(self, operation: str) -> None:
        if operation not in OPERATION_STAGES:
            operation = "scan"
        self._operation = operation
        self._stages = OPERATION_STAGES[operation]
        self._stage_order = [sid for sid, _ in self._stages]
        self.remove_class("mode-scan", "mode-audit")
        self.add_class(f"mode-{operation}")

    def reset(self) -> None:
        self._completed = set()
        self._active_stage = "init"
        self._current_message = ""
        self._detail_text = ""
        self._note = ""
        self._frame_idx = 0
        self._stage_started_at = time.monotonic()
        self._files_total = None
        self._files_done = None
        self._chunks_total = None
        self._chunks_done = None
        self.query_one("#progress-stages", Static).update(self._render_stages())
        self.query_one("#progress-current", Static).update(self._render_current_stage())
        self.query_one("#progress-detail", Static).update("")
        self.query_one("#progress-note", Static).update("")
        self.query_one("#progress-bar", ProgressBar).update(total=len(self._stage_order), progress=0)

    def show(self, operation: str | None = None) -> None:
        if operation:
            self.set_operation(operation)
        self.remove_class("hidden")
        self.remove_class("scanning", "auditing")
        self.add_class("scanning" if self._operation == "scan" else "auditing")
        self.reset()
        titles = _OPERATION_TITLES[self._operation]
        self.query_one("#progress-title", Static).update(titles["active"])
        self._start_spinner()

    def hide(self) -> None:
        self._stop_spinner()
        self.remove_class("scanning", "auditing")
        self.add_class("hidden")

    def _start_spinner(self) -> None:
        self._stop_spinner()
        self._frame_idx = 0
        self._spinner_timer = self.set_interval(0.12, self._tick_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def _tick_spinner(self) -> None:
        self._frame_idx = (self._frame_idx + 1) % len(_SPINNER_FRAMES)
        self.query_one("#progress-stages", Static).update(self._render_stages())
        self.query_one("#progress-current", Static).update(self._render_current_stage())
        self.query_one("#progress-detail", Static).update(self._render_detail_line())

    def _active_icon(self, stage_id: str) -> str:
        if stage_id in self._completed:
            return "[green]v[/green]"
        if stage_id == self._active_stage:
            if stage_id == "done":
                return "[green]v[/green]"
            frame = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]
            return f"[bold cyan]{frame}[/bold cyan]"
        return "[dim]-[/dim]"

    def _stage_label(self, stage_id: str) -> str:
        for sid, label in self._stages:
            if sid == stage_id:
                return label
        return stage_id

    def _render_stages(self) -> str:
        lines: list[str] = []
        for stage_id, label in self._stages:
            lines.append(f"{self._active_icon(stage_id)} {label}")
        return "\n".join(lines)

    def _render_current_stage(self) -> str:
        if self._current_message:
            text = self._current_message
        else:
            text = self._stage_label(self._active_stage)
        return f"{self._active_icon(self._active_stage)} {text}"

    def _render_detail_line(self) -> str:
        parts: list[str] = []
        if self._detail_text:
            parts.append(self._detail_text)
        elif self._current_message:
            parts.append(self._current_message)

        if self._files_total is not None and self._files_done is not None:
            parts.append(f"Files: {self._files_done}/{self._files_total}")

        if self._chunks_total is not None and self._chunks_done is not None:
            parts.append(f"Chunks: {self._chunks_done}/{self._chunks_total}")

        if self._active_stage != "done":
            elapsed = int(time.monotonic() - self._stage_started_at)
            if elapsed >= 2:
                parts.append(f"{elapsed}s")

        if parts:
            return " | ".join(parts)
        return "[dim]Working...[/dim]"

    def _scroll_to_active_stage(self) -> None:
        if self._active_stage not in self._stage_order:
            return
        try:
            scroll = self.query_one("#progress-stages-scroll", VerticalScroll)
            stage_idx = self._stage_order.index(self._active_stage)
            scroll.scroll_to(y=stage_idx, animate=False, force=True)
        except Exception:
            pass

    def _set_active_stage(self, stage: str) -> None:
        if stage != self._active_stage:
            self._stage_started_at = time.monotonic()
        self._active_stage = stage

    def _update_progress_bar(self, data: dict) -> None:
        bar = self.query_one("#progress-bar", ProgressBar)
        total_steps = max(len(self._stage_order) - 1, 1)

        if self._active_stage == "done":
            bar.update(total=total_steps, progress=total_steps)
            return

        stage_idx = (
            self._stage_order.index(self._active_stage)
            if self._active_stage in self._stage_order
            else 0
        )
        bar.update(total=total_steps, progress=stage_idx)

        chunks_total = data.get("chunks_total")
        chunks_done = data.get("chunks_done")
        if chunks_total is not None and chunks_total > 0:
            bar.update(total=chunks_total, progress=chunks_done or 0)

    def update_from_event(self, stage: str, data: dict) -> None:
        if not hasattr(self, "_completed"):
            self.reset()

        if stage == "llm_status":
            provider = data.get("llm_provider", "none")
            model = data.get("llm_model", "")
            uses_llm = data.get("scan_uses_llm", False)
            if data.get("llm_configured"):
                self._note = (
                    f"AI: {provider} / {model} — "
                    f"{'reading codebase with presets + rules' if uses_llm else 'ready'}"
                )
            else:
                self._note = "AI not configured — scan requires Cloud API or Ollama."
            self.query_one("#progress-note", Static).update(self._note)

        stage_idx = self._stage_order.index(stage) if stage in self._stage_order else -1
        if stage_idx >= 0:
            for prior in self._stage_order[:stage_idx]:
                self._completed.add(prior)
            self._set_active_stage(stage)
            if stage == "done":
                self._completed.add("done")
                self._set_active_stage("done")
                self._stop_spinner()
                titles = _OPERATION_TITLES[self._operation]
                self.query_one("#progress-title", Static).update(titles["done"])

        message = data.get("message")
        if message:
            self._current_message = str(message)
            self._stage_started_at = time.monotonic()

        detail = data.get("detail")
        current_file = data.get("current_file")
        issues = data.get("issues_found")
        detail_parts: list[str] = []
        if detail:
            detail_parts.append(str(detail))
        elif message:
            detail_parts.append(str(message))
        if current_file:
            detail_parts.append(f"Current: {current_file}")
        if issues is not None:
            detail_parts.append(f"Issues: {issues}")
        self._detail_text = " | ".join(detail_parts)

        files_total = data.get("files_total")
        files_done = data.get("files_done")
        self._files_total = files_total
        self._files_done = files_done

        chunks_total = data.get("chunks_total")
        chunks_done = data.get("chunks_done")
        self._chunks_total = chunks_total
        self._chunks_done = chunks_done

        self._update_progress_bar(data)
        self.query_one("#progress-stages", Static).update(self._render_stages())
        self.query_one("#progress-current", Static).update(self._render_current_stage())
        self.query_one("#progress-detail", Static).update(self._render_detail_line())
        self._scroll_to_active_stage()


# Backward-compatible alias used by the TUI app.
ScanProgressPanel = OperationProgressPanel