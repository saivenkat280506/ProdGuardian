import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prodguardian.llm.codebase_scanner import (
    CodebaseLLMScanner,
    build_codebase_scan_prompt,
    build_file_chunks,
    collect_scannable_files,
    parse_llm_scan_response,
)
from prodguardian.tui.settings_store import get_presets, get_rules


@pytest.fixture
def sample_project(tmp_path):
    project = tmp_path / "myapp"
    project.mkdir()
    (project / "config.py").write_text('API_KEY = "sk-live-secret-key-12345"\n')
    (project / "app.py").write_text("print('debug')\n")
    return project


def test_collect_scannable_files(sample_project):
    files = collect_scannable_files(sample_project, skip_test_dirs=False)
    names = {f.name for f in files}
    assert "config.py" in names
    assert "app.py" in names


def test_build_file_chunks(sample_project):
    files = collect_scannable_files(sample_project, skip_test_dirs=False)
    chunks = build_file_chunks(sample_project, files)
    assert len(chunks) >= 1
    assert any("config.py" in rel for chunk in chunks for rel, _ in chunk)


def test_build_codebase_scan_prompt_includes_presets_rules():
    presets = [{"name": "Secrets", "items": ["sk-"], "enabled": True}]
    rules = [
        {
            "name": "No secrets",
            "instruction": "Find hardcoded secrets",
            "preset_names": ["Secrets"],
            "enabled": True,
        }
    ]
    prompt = build_codebase_scan_prompt([("app.py", "x = 1")], presets, rules, "demo")
    assert "Secrets" in prompt
    assert "No secrets" in prompt
    assert "app.py" in prompt
    assert "JSON array" in prompt


def test_parse_llm_scan_response_json_array(sample_project):
    raw = json.dumps(
        [
            {
                "rule_id": "LLM001",
                "severity": "CRITICAL",
                "file": "config.py",
                "line": 1,
                "message": "Hardcoded API key",
                "code_snippet": 'API_KEY = "sk-..."',
            }
        ]
    )
    issues = parse_llm_scan_response(raw, sample_project)
    assert len(issues) == 1
    assert issues[0]["rule_id"] == "LLM001"
    assert issues[0]["severity"] == "CRITICAL"


def test_parse_llm_scan_response_markdown_fence(sample_project):
    raw = """Here are the issues:
```json
[{"rule_id": "LLM001", "severity": "HIGH", "file": "app.py", "line": 1, "message": "Debug print", "code_snippet": "print"}]
```"""
    issues = parse_llm_scan_response(raw, sample_project)
    assert len(issues) == 1


@patch("prodguardian.llm.codebase_scanner.ScanLLMRouter")
def test_codebase_llm_scanner_calls_llm(mock_router_cls, sample_project):
    mock_router = MagicMock()
    mock_router.budget_model.return_value = "gpt-3.5-turbo"
    mock_router.api_calls_made.return_value = 1
    mock_router.complete_mono.return_value = json.dumps(
        [
            {
                "rule_id": "LLM001",
                "severity": "CRITICAL",
                "file": "config.py",
                "line": 1,
                "message": "Exposed API key",
                "code_snippet": "API_KEY",
            }
        ]
    )
    mock_router_cls.return_value = mock_router

    scanner = CodebaseLLMScanner(
        sample_project,
        get_presets(),
        get_rules(),
        model="gpt-3.5-turbo",
        api_key="test-key",
        max_cost_usd=1.0,
        skip_test_dirs=False,
    )
    events: list[str] = []
    report = scanner.scan(on_progress=lambda s, d: events.append(s))

    assert mock_router.complete_mono.called
    assert len(report.issues) >= 1
    assert report.api_calls == 1
    assert "llm_scan" in events
    assert report.issues[0]["agent"] == "LLMScanner"