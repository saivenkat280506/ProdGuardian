import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prodguardian.tui.orchestrator import Orchestrator, VIBE_LEAK_RULES


@pytest.fixture
def orchestrator(tmp_path):
    return Orchestrator(tmp_path)


def test_wants_project_picker_for_bare_scan(orchestrator):
    assert orchestrator.wants_project_picker("scan") == "scan"
    assert orchestrator.wants_project_picker("SCAN") == "scan"
    assert orchestrator.wants_project_picker("audit") == "audit"


def test_wants_project_picker_false_for_scan_with_path(orchestrator):
    assert orchestrator.wants_project_picker("scan ./app") is None


def test_parse_scan_path(orchestrator, tmp_path):
    project = tmp_path / "my-app"
    project.mkdir()
    parsed = orchestrator.parse_scan_path(f"scan {project}")
    assert parsed == project.resolve()


def test_parse_scan_path_missing_dir(orchestrator, tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="not found"):
        orchestrator.parse_scan_path(f"scan {missing}")


def test_parse_audit_path(orchestrator, tmp_path):
    project = tmp_path / "my-app"
    project.mkdir()
    parsed = orchestrator.parse_audit_path(f"audit {project}")
    assert parsed == project.resolve()


def test_wants_project_picker_false_for_audit_with_path(orchestrator, tmp_path):
    project = tmp_path / "my-app"
    project.mkdir()
    assert orchestrator.wants_project_picker(f"audit {project}") is None


@patch("prodguardian.production.auditor.ProductionAuditor")
def test_handle_audit_with_path(mock_auditor_cls, orchestrator, tmp_path):
    project = tmp_path / "my-app"
    project.mkdir()
    mock_auditor_cls.return_value.audit.return_value = [
        {
            "rule_id": "PROD001",
            "message": "Missing Dockerfile - cannot containerize",
        }
    ]

    result = asyncio.run(orchestrator.handle(f"audit {project}"))

    assert orchestrator.root == project.resolve()
    assert "FAILED" in result
    assert "PROD001" in result
    assert "Missing Dockerfile" in result
    mock_auditor_cls.assert_called_once_with(project.resolve())


def test_set_project_updates_root(orchestrator, tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    orchestrator.set_project(project)
    assert orchestrator.root == project.resolve()


@patch("prodguardian.tui.orchestrator.is_llm_configured", return_value=True)
@patch("prodguardian.tui.orchestrator.Orchestrator._build_llm_scanner")
def test_run_scan_highlights_vibe_leaks(mock_build_scanner, _mock_configured):
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "python_vuln"
    orchestrator = Orchestrator(fixture_root)
    orchestrator.config.setdefault("scan", {})["skip_test_dirs"] = False

    mock_scanner = MagicMock()
    mock_scanner.scan.return_value = [
        {
            "rule_id": "LLM001",
            "severity": "CRITICAL",
            "file": str(fixture_root / "bad.py"),
            "line": 2,
            "message": "Hardcoded API key must not ship",
            "code_snippet": "API_KEY",
        }
    ]
    mock_build_scanner.return_value = mock_scanner

    result = asyncio.run(orchestrator._run_scan())

    assert "vibe-coded leak" in result.lower()
    assert "LLM001" in result
    assert str(fixture_root) in result


def test_vibe_leak_rules_include_core_leaks():
    assert "SEC001" in VIBE_LEAK_RULES
    assert "LEAK001" in VIBE_LEAK_RULES
    assert "DEV001" in VIBE_LEAK_RULES
    assert "LLM001" in VIBE_LEAK_RULES