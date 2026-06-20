from unittest.mock import patch

from prodguardian.utils.clipboard import copy_report_text, strip_rich_markup


def test_strip_rich_markup():
    plain = strip_rich_markup(
        "[bold red]CRITICAL[/bold red] leak in [cyan]config.py[/cyan]"
    )
    assert plain == "CRITICAL leak in config.py"
    assert "[" not in plain


@patch("prodguardian.utils.clipboard.copy_to_system_clipboard", return_value=True)
def test_copy_report_text_uses_system_clipboard(mock_copy):
    terminal = []
    ok = copy_report_text(
        "[bold]Scan Results[/bold]",
        terminal_copy=terminal.append,
    )
    assert ok is True
    mock_copy.assert_called_once()
    assert terminal == []


@patch("prodguardian.utils.clipboard.copy_to_system_clipboard", return_value=False)
def test_copy_report_text_falls_back_to_terminal(mock_copy):
    terminal = []
    ok = copy_report_text(
        "[bold]Audit[/bold]",
        terminal_copy=terminal.append,
    )
    assert ok is True
    assert terminal == ["Audit"]