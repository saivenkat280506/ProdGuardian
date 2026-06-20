"""Editable scan rules list with templates and + for custom rules."""

from __future__ import annotations

import uuid
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from prodguardian.tui.styles import GLOBAL_CSS


class RuleRow(Widget):
    """One rule: name + instruction + linked preset names."""

    DEFAULT_CSS = """
    RuleRow {
        height: auto;
        margin-bottom: 1;
        border-bottom: solid $accent;
        padding-bottom: 1;
    }
    RuleRow Horizontal {
        width: 100%;
        align: left middle;
    }
    RuleRow .rule-name {
        width: 1fr;
        min-width: 14;
    }
    RuleRow .rule-presets {
        width: 1fr;
        min-width: 14;
    }
    RuleRow .rule-instruction {
        width: 100%;
        margin-top: 1;
    }
    RuleRow .tpl-badge {
        width: auto;
        min-width: 10;
        color: $foreground-muted;
    }
    RuleRow .remove-btn {
        min-width: 4;
        width: auto;
    }
    """

    def __init__(self, rule: dict[str, Any], *, can_delete: bool = True):
        super().__init__()
        self._rule = rule
        self._can_delete = can_delete

    def compose(self) -> ComposeResult:
        badge = "[template]" if self._rule.get("builtin") else ""
        with Vertical():
            with Horizontal():
                if badge:
                    yield Static(badge, classes="tpl-badge")
                yield Input(
                    value=self._rule.get("name", ""),
                    placeholder="Rule name",
                    classes="rule-name",
                )
                if self._can_delete:
                    yield Button("×", variant="error", classes="remove-btn")
            yield Input(
                value=", ".join(self._rule.get("preset_names", [])),
                placeholder="Preset names to check (comma-separated)",
                classes="rule-presets",
            )
            yield Input(
                value=self._rule.get("instruction", ""),
                placeholder="What to check in the codebase using those presets...",
                classes="rule-instruction",
            )

    def to_dict(self) -> dict[str, Any]:
        name = self.query_one(".rule-name", Input).value.strip()
        presets_raw = self.query_one(".rule-presets", Input).value
        instruction = self.query_one(".rule-instruction", Input).value.strip()
        preset_names = [part.strip() for part in presets_raw.split(",") if part.strip()]
        return {
            "id": self._rule.get("id", f"rule_{uuid.uuid4().hex[:8]}"),
            "name": name or "Custom rule",
            "instruction": instruction,
            "preset_names": preset_names,
            "builtin": self._rule.get("builtin", False),
            "enabled": True,
        }


class RuleEditor(Widget):
    """Rule manager used on the Settings page."""

    DEFAULT_CSS = (
        GLOBAL_CSS
        + """
    RuleEditor {
        layout: vertical;
        height: 100%;
        color: $foreground;
    }
    #rule-hint {
        height: auto;
        max-height: 2;
        margin-bottom: 1;
    }
    #rule-scroll {
        height: 1fr;
        min-height: 6;
        width: 100%;
        border: none;
        padding: 0;
        margin-bottom: 1;
        background: transparent;
    }
    #add-rule-btn {
        width: 100%;
        height: 3;
        min-height: 3;
        max-height: 3;
    }
    """
    )

    def __init__(self, rules: list[dict[str, Any]] | None = None, *, id: str | None = None):
        super().__init__(id=id)
        self._initial = rules or []

    def compose(self) -> ComposeResult:
        yield Static(
            "Rules define what to check. They are fed into cloud/Ollama context with your presets.",
            id="rule-hint",
        )
        yield VerticalScroll(id="rule-scroll")
        yield Button("+ Add Rule", id="add-rule-btn", variant="primary")

    def on_mount(self) -> None:
        scroll = self.query_one("#rule-scroll", VerticalScroll)
        for rule in self._initial:
            scroll.mount(RuleRow(rule, can_delete=not rule.get("builtin", False)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-rule-btn":
            self._add_custom()
            return
        if "remove-btn" in event.button.classes:
            row = event.button.parent.parent.parent
            row.remove()

    def _add_custom(self) -> None:
        scroll = self.query_one("#rule-scroll", VerticalScroll)
        scroll.mount(
            RuleRow(
                {
                    "id": f"rule_{uuid.uuid4().hex[:8]}",
                    "name": "",
                    "instruction": "",
                    "preset_names": [],
                    "builtin": False,
                },
                can_delete=True,
            )
        )

    def collect(self) -> list[dict[str, Any]]:
        scroll = self.query_one("#rule-scroll", VerticalScroll)
        rules: list[dict[str, Any]] = []
        for child in scroll.children:
            if isinstance(child, RuleRow):
                data = child.to_dict()
                if data.get("instruction"):
                    rules.append(data)
        return rules