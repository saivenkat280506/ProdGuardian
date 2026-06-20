from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prodguardian.tui.orchestrator import Orchestrator


@pytest.fixture
def leaky_project(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "config.py").write_text('API_KEY = "sk-live-leaked-secret-key"\n')
    (project / "main.py").write_text("print('debug')\n")
    return project


@patch("prodguardian.tui.orchestrator.is_llm_configured", return_value=False)
def test_scan_finds_leaks_without_llm(mock_configured, leaky_project):
    orch = Orchestrator(leaky_project)
    orch.set_project(leaky_project)
    result = orch._run_scan_blocking()
    assert "no vibe-coded leaks" not in result.lower()
    assert "sk-live" in result.lower() or "SEC001" in result or "PRESET001" in result
    assert len(orch.scan_results) >= 1


@patch("prodguardian.tui.orchestrator.is_llm_configured", return_value=True)
@patch("prodguardian.llm.llm_router.prepare_scan_models", return_value=None)
@patch("prodguardian.llm.codebase_scanner.CodebaseLLMScanner")
def test_scan_reports_no_api_calls(mock_scanner_cls, _prep, _cfg, leaky_project):
    from prodguardian.llm.codebase_scanner import ScanReport

    mock_scanner = MagicMock()
    mock_scanner.scan.return_value = ScanReport(
        issues=[],
        files_found=2,
        chunks_total=5,
        chunks_scanned=0,
        api_calls=0,
        stopped_early=True,
        stop_reason="Budget limit reached: Token limit (32000) exceeded",
    )
    mock_scanner_cls.return_value = mock_scanner

    orch = Orchestrator(leaky_project)
    orch.set_project(leaky_project)
    result = orch._run_scan_blocking()

    assert "did not reach the API" in result
    assert len(orch.scan_results) == 0 or "Local scan still found" in result