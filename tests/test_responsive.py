from textual.geometry import Size

from prodguardian.tui.responsive import (
    MODE_COMPACT,
    MODE_COMFORTABLE,
    MODE_EXPANDED,
    layout_mode,
)


def test_layout_mode_compact():
    assert layout_mode(Size(60, 24)) == MODE_COMPACT


def test_layout_mode_comfortable():
    assert layout_mode(Size(100, 35)) == MODE_COMFORTABLE


def test_layout_mode_expanded():
    assert layout_mode(Size(120, 45)) == MODE_EXPANDED