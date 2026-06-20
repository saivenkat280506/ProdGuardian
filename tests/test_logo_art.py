from prodguardian.tui.logo_art import FULL_WIDTH, _load_full_logo, logo_for_terminal


def test_full_logo_lines_are_uniform_width():
    lines = [line for line in _load_full_logo().splitlines() if line]
    assert lines
    assert all(len(line) == FULL_WIDTH for line in lines)


def test_logo_for_terminal_compact_on_narrow_width():
    logo = logo_for_terminal(60, 40, "layout-comfortable")
    assert "ProdGuardian" in logo


def test_logo_for_terminal_full_on_normal_terminal():
    logo = logo_for_terminal(100, 40, "layout-expanded")
    assert "████" in logo
    assert "Production Readiness" in logo