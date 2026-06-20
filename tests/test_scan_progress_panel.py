import time

from prodguardian.tui.widgets.scan_progress import OperationProgressPanel


def test_render_stages_shows_active_spinner():
    panel = OperationProgressPanel(operation="scan")
    panel._completed = {"init"}
    panel._active_stage = "discover"
    panel._frame_idx = 0

    rendered = panel._render_stages()

    assert "[bold cyan]|[/bold cyan]" in rendered
    assert "[green]v[/green] Initialize scan" in rendered
    assert "[dim]-[/dim] Connect AI provider" in rendered


def test_audit_mode_uses_audit_stage_labels():
    panel = OperationProgressPanel(operation="audit")
    panel._completed = {"init", "core", "runtime"}
    panel._active_stage = "security"
    panel._frame_idx = 1

    rendered = panel._render_current_stage()

    assert "Security configuration" in rendered
    assert "[bold cyan]/[/bold cyan]" in rendered


def test_current_stage_shows_live_message_when_available():
    panel = OperationProgressPanel(operation="audit")
    panel._active_stage = "runtime"
    panel._current_message = "Checking Health endpoints... (3/7)"
    panel._frame_idx = 0

    rendered = panel._render_current_stage()

    assert "Checking Health endpoints... (3/7)" in rendered
    assert "Runtime & reliability" not in rendered


def test_render_detail_line_includes_elapsed_seconds():
    panel = OperationProgressPanel(operation="audit")
    panel._active_stage = "runtime"
    panel._current_message = "Checking Security headers... (1/4)"
    panel._stage_started_at = time.monotonic() - 5

    rendered = panel._render_detail_line()

    assert "5s" in rendered


def test_update_progress_bar_uses_stage_index_for_audit():
    panel = OperationProgressPanel(operation="audit")
    panel._active_stage = "security"

    class FakeBar:
        total = None
        progress = 0
        calls: list[tuple] = []

        def update(self, *, total=None, progress=0):
            self.calls.append((total, progress))

    fake_bar = FakeBar()
    panel.query_one = lambda selector, expected_type=None: fake_bar  # type: ignore[method-assign]

    panel._update_progress_bar({})

    assert fake_bar.calls[-1] == (6, 3)


def test_update_from_event_marks_done_stage():
    panel = OperationProgressPanel(operation="scan")
    panel._completed = set()
    panel._active_stage = "aggregate"
    panel._note = ""
    panel._frame_idx = 0
    panel._stop_spinner = lambda: None  # type: ignore[method-assign]
    panel.query_one = lambda selector, expected_type=None: _FakeWidget()  # type: ignore[method-assign]

    panel.update_from_event("done", {"message": "Finished"})

    assert panel._active_stage == "done"
    assert "done" in panel._completed


class _FakeWidget:
    total = None
    progress = 0

    def update(self, *_args, **_kwargs) -> None:
        pass