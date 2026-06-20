"""Scan progress reporting for CLI and TUI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ProgressCallback = Callable[[str, dict[str, Any]], None]

SCAN_STAGES: list[tuple[str, str]] = [
    ("init", "Initialize scan"),
    ("static_scan", "Local preset + agent scan"),
    ("presets", "Match vibe presets"),
    ("agents", "Run security agents"),
    ("llm_status", "Connect AI provider"),
    ("discover", "Discover project files"),
    ("llm_scan", "AI codebase analysis"),
    ("aggregate", "Build scan report"),
    ("done", "Complete"),
]

AUDIT_STAGES: list[tuple[str, str]] = [
    ("init", "Initialize audit"),
    ("core", "Core production assets"),
    ("runtime", "Runtime & reliability"),
    ("security", "Security configuration"),
    ("ops", "Monitoring & operations"),
    ("report", "Build audit report"),
    ("done", "Complete"),
]

OPERATION_STAGES = {
    "scan": SCAN_STAGES,
    "audit": AUDIT_STAGES,
}


@dataclass
class ScanProgressReporter:
    """Emit structured progress events to an optional callback."""

    on_progress: ProgressCallback | None = None
    _issues_found: int = field(default=0, init=False)

    def emit(self, stage: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Accept emit(stage, key=val) or callback style emit(stage, {dict})."""
        if isinstance(data, dict):
            payload = {"stage": stage, **data, **kwargs}
        else:
            payload = {"stage": stage, **kwargs}
            if data is not None:
                payload["message"] = str(data)
        if self.on_progress:
            self.on_progress(stage, payload)

    def add_issues(self, count: int) -> None:
        self._issues_found += count

    @property
    def issues_found(self) -> int:
        return self._issues_found