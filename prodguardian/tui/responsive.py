"""Responsive layout helpers for small and large terminals."""

from __future__ import annotations

from textual.geometry import Size

MODE_COMPACT = "layout-compact"
MODE_COMFORTABLE = "layout-comfortable"
MODE_EXPANDED = "layout-expanded"

ALL_MODES = (MODE_COMPACT, MODE_COMFORTABLE, MODE_EXPANDED)


def layout_mode(size: Size) -> str:
    """Pick a layout class from terminal dimensions."""
    if size.height < 30 or size.width < 72:
        return MODE_COMPACT
    if size.height >= 42 and size.width >= 110:
        return MODE_EXPANDED
    return MODE_COMFORTABLE


def apply_layout_mode(widget, size: Size) -> str:
    """Set layout-* class on a widget; return the active mode."""
    mode = layout_mode(size)
    for cls in ALL_MODES:
        widget.remove_class(cls)
    widget.add_class(mode)
    return mode