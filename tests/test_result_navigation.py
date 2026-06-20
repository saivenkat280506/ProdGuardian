from prodguardian.tui.screens.project_picker import _PICKER_COPY
from prodguardian.tui.screens.result_view import ResultViewScreen, _RESULT_ACTIONS


def test_project_picker_has_scan_and_audit_copy():
    assert "scan" in _PICKER_COPY
    assert "audit" in _PICKER_COPY
    assert _PICKER_COPY["scan"]["confirm"] == "Scan Project"
    assert _PICKER_COPY["audit"]["confirm"] == "Audit Project"


def test_result_view_repeat_actions_for_scan_and_audit():
    assert _RESULT_ACTIONS["scan"]["repeat_label"] == "Scan Another Folder"
    assert _RESULT_ACTIONS["audit"]["repeat_label"] == "Audit Another Folder"
    assert _RESULT_ACTIONS["scan"]["repeat_value"] == "repeat"
    assert _RESULT_ACTIONS["audit"]["repeat_value"] == "repeat"


def test_result_view_plain_text_for_clipboard():
    screen = ResultViewScreen(
        "Scan Results",
        "/tmp/demo",
        "[bold]Found 2 leak(s)[/bold]\n  - `SEC001` in config.py:1",
        kind="scan",
    )
    plain = screen._report_plain_text()
    assert plain.startswith("Scan Results\nProject: /tmp/demo\n\n")
    assert "Found 2 leak(s)" in plain
    assert "[bold]" not in plain
    assert "SEC001" in plain


def test_result_view_copy_binding_present():
    actions = {binding[1] for binding in ResultViewScreen.BINDINGS}
    assert "copy_report" in actions