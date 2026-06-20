"""Editable preset list with built-in templates and + for custom entries."""

from __future__ import annotations

import uuid
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select, Static

from prodguardian.scan.presets_data import PRESET_CATEGORIES, VALID_SEVERITIES
from prodguardian.tui.styles import GLOBAL_CSS

_SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
_SEVERITY_OPTIONS = [(s, s) for s in _SEVERITY_ORDER if s in VALID_SEVERITIES]
_CATEGORY_OPTIONS = [(c, c) for c in PRESET_CATEGORIES]


class PresetRow(Widget):
    """One preset: name, keywords, optional category/severity/description."""

    DEFAULT_CSS = """
    PresetRow {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        border-bottom: solid $accent;
        padding-bottom: 1;
    }
    PresetRow Horizontal {
        width: 100%;
        align: left middle;
    }
    PresetRow .preset-name {
        width: 1fr;
        max-width: 22;
        min-width: 12;
    }
    PresetRow .preset-items {
        width: 2fr;
        min-width: 16;
    }
    PresetRow .preset-meta {
        width: auto;
        min-width: 14;
        max-width: 22;
    }
    PresetRow .preset-desc {
        width: 100%;
        height: auto;
        color: $foreground-muted;
        margin-top: 1;
    }
    PresetRow .tpl-badge {
        width: auto;
        min-width: 10;
        color: $foreground-muted;
    }
    PresetRow .remove-btn {
        min-width: 4;
        width: auto;
    }
    """

    def __init__(self, preset: dict[str, Any], *, can_delete: bool = True):
        super().__init__()
        self._preset = preset
        self._can_delete = can_delete

    def compose(self) -> ComposeResult:
        badge = "[template]" if self._preset.get("builtin") else ""
        with Vertical():
            with Horizontal():
                if badge:
                    yield Static(badge, classes="tpl-badge")
                yield Input(
                    value=self._preset.get("name", ""),
                    placeholder="Preset name",
                    classes="preset-name",
                )
                yield Input(
                    value=", ".join(self._preset.get("items", [])),
                    placeholder="keywords, packages, code patterns...",
                    classes="preset-items",
                )
                if self._can_delete:
                    yield Button("×", variant="error", classes="remove-btn")
            with Horizontal():
                yield Label("Category:", classes="tpl-badge")
                if self._preset.get("builtin"):
                    yield Static(
                        self._preset.get("category", "General"),
                        classes="preset-meta",
                    )
                else:
                    yield Select(
                        _CATEGORY_OPTIONS,
                        value=self._preset.get("category", PRESET_CATEGORIES[0]),
                        allow_blank=False,
                        classes="preset-meta",
                        id=f"cat-{self._preset.get('id', 'new')}",
                    )
                yield Label("Severity:", classes="tpl-badge")
                if self._preset.get("builtin"):
                    yield Static(
                        self._preset.get("severity", "HIGH"),
                        classes="preset-meta",
                    )
                else:
                    yield Select(
                        _SEVERITY_OPTIONS,
                        value=self._preset.get("severity", "HIGH"),
                        allow_blank=False,
                        classes="preset-meta",
                        id=f"sev-{self._preset.get('id', 'new')}",
                    )
            desc = self._preset.get("description", "")
            if desc:
                rec = " ★ Recommended" if self._preset.get("recommended") else ""
                yield Static(f"{desc}{rec}", classes="preset-desc")

    def to_dict(self) -> dict[str, Any]:
        name = self.query_one(".preset-name", Input).value.strip()
        raw_items = self.query_one(".preset-items", Input).value
        items = [part.strip() for part in raw_items.split(",") if part.strip()]
        row: dict[str, Any] = {
            "id": self._preset.get("id", f"custom_{uuid.uuid4().hex[:8]}"),
            "name": name or "Custom preset",
            "items": items,
            "builtin": self._preset.get("builtin", False),
            "enabled": True,
        }
        if self._preset.get("builtin"):
            row["category"] = self._preset.get("category", "General")
            row["severity"] = self._preset.get("severity", "HIGH")
            row["description"] = self._preset.get("description", "")
            if self._preset.get("recommended"):
                row["recommended"] = True
        else:
            for child in self.query(Select):
                sid = child.id or ""
                if sid.startswith("cat-"):
                    row["category"] = str(child.value)
                elif sid.startswith("sev-"):
                    row["severity"] = str(child.value)
            row.setdefault("category", PRESET_CATEGORIES[0])
            row.setdefault("severity", "HIGH")
        return row


class PresetEditor(Widget):
    """Preset manager used on the Settings page."""

    DEFAULT_CSS = (
        GLOBAL_CSS
        + """
    PresetEditor {
        layout: vertical;
        height: 100%;
        color: $foreground;
    }
    #preset-hint {
        height: auto;
        max-height: 3;
        margin-bottom: 1;
    }
    #preset-scroll {
        height: 1fr;
        min-height: 6;
        width: 100%;
        border: none;
        padding: 0;
        margin-bottom: 1;
        background: transparent;
    }
    #add-preset-btn {
        width: 100%;
        height: 3;
        min-height: 3;
        max-height: 3;
    }
    """
    )

    def __init__(self, presets: list[dict[str, Any]] | None = None, *, id: str | None = None):
        super().__init__(id=id)
        self._initial = presets or []

    def compose(self) -> ComposeResult:
        yield Static(
            "Keywords and patterns for AI Scan. Built-ins include category, severity, and "
            "description. Custom presets can set category and severity below.",
            id="preset-hint",
        )
        yield VerticalScroll(id="preset-scroll")
        yield Button("+ Add Preset", id="add-preset-btn", variant="primary")

    def on_mount(self) -> None:
        scroll = self.query_one("#preset-scroll", VerticalScroll)
        for preset in self._initial:
            scroll.mount(PresetRow(preset, can_delete=not preset.get("builtin", False)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-preset-btn":
            self._add_custom()
            return
        if "remove-btn" in event.button.classes:
            event.button.parent.parent.remove()

    def _add_custom(self) -> None:
        scroll = self.query_one("#preset-scroll", VerticalScroll)
        scroll.mount(
            PresetRow(
                {
                    "id": f"custom_{uuid.uuid4().hex[:8]}",
                    "name": "",
                    "items": [],
                    "category": PRESET_CATEGORIES[0],
                    "severity": "HIGH",
                    "builtin": False,
                },
                can_delete=True,
            )
        )

    def collect(self) -> list[dict[str, Any]]:
        scroll = self.query_one("#preset-scroll", VerticalScroll)
        presets: list[dict[str, Any]] = []
        for child in scroll.children:
            if isinstance(child, PresetRow):
                data = child.to_dict()
                if data.get("items"):
                    presets.append(data)
        return presets