import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from prodguardian.agents.manager import AgentManager
from prodguardian.scan.preset_scanner import scan_tree_presets
from prodguardian.tui.orchestrator import Orchestrator


def test_agent_manager_emits_progress(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "main.py").write_text('API_KEY = "sk-test123"\n')

    events: list[tuple[str, dict]] = []

    def on_progress(stage: str, data: dict) -> None:
        events.append((stage, data))

    manager = AgentManager(project, skip_test_dirs=False)
    manager.scan(on_progress=on_progress)

    assert any(stage == "agents" for stage, _ in events)
    assert events[0][1].get("message", "").startswith("Running")


def test_scan_tree_presets_emits_progress(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "main.py").write_text("console.log('debug')\n")

    presets = [
        {
            "name": "Debug Code",
            "items": ["console.log"],
            "enabled": True,
        }
    ]
    events: list[str] = []

    def on_progress(stage: str, data: dict) -> None:
        events.append(stage)

    issues = scan_tree_presets(project, presets, lambda _: False, on_progress=on_progress)
    assert len(issues) >= 1
    assert "presets" in events


@patch("prodguardian.tui.orchestrator.is_llm_configured", return_value=True)
@patch("prodguardian.tui.orchestrator.Orchestrator._build_llm_scanner")
def test_orchestrator_scan_reports_llm_status(mock_build_scanner, _mock_configured, tmp_path):
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
            "message": "Hardcoded API key",
            "code_snippet": "API_KEY",
        }
    ]
    mock_build_scanner.return_value = mock_scanner

    stages: list[str] = []

    def on_progress(stage: str, data: dict) -> None:
        stages.append(stage)

    result = asyncio.run(orchestrator._run_scan(on_progress=on_progress))

    assert "llm_status" in stages
    assert "llm_scan" not in stages  # scanner.scan mocked — emits from scanner internally
    assert "done" in stages
    assert "LLM001" in result
    mock_scanner.scan.assert_called_once()