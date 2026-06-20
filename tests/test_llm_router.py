import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prodguardian.llm.llm_router import (
    SCAN_MODE_HYBRID,
    SCAN_MODE_MONO,
    ScanLLMSettings,
    detect_provider_from_model,
    normalize_model_string,
    prepare_scan_models,
    resolve_scan_llm_settings,
)
from prodguardian.llm.codebase_scanner import (
    CodebaseLLMScanner,
    build_analyzer_prompt,
    build_reporter_prompt,
)
from prodguardian.tui.settings_store import get_presets, get_rules


def test_detect_provider_from_model():
    assert detect_provider_from_model("ollama/llama3.2:3b") == "ollama"
    assert detect_provider_from_model("groq/llama-3.3-70b-versatile") == "groq"
    assert detect_provider_from_model("openai/gpt-4o-mini") == "openai"
    assert detect_provider_from_model("gpt-3.5-turbo") == "openai"


def test_normalize_model_string_adds_ollama_prefix():
    assert normalize_model_string("llama3.2:3b") == "ollama/llama3.2:3b"
    assert normalize_model_string("groq/llama-3.3-70b-versatile") == "groq/llama-3.3-70b-versatile"


def test_resolve_scan_llm_settings_defaults_to_mono(monkeypatch):
    monkeypatch.delenv("PRODGUARDIAN_MODEL", raising=False)
    monkeypatch.delenv("PRODGUARDIAN_SCAN_MODE", raising=False)
    settings = resolve_scan_llm_settings({"model": "gpt-3.5-turbo", "api_key": "k"})
    assert settings.mode == SCAN_MODE_MONO
    assert settings.mono_model == "gpt-3.5-turbo"


def test_resolve_scan_llm_settings_hybrid(monkeypatch):
    monkeypatch.delenv("PRODGUARDIAN_SCAN_MODE", raising=False)
    settings = resolve_scan_llm_settings(
        {
            "scan_mode": "hybrid",
            "model": "gpt-3.5-turbo",
            "analyzer_model": "groq/llama-3.3-70b-versatile",
            "reporter_model": "groq/llama-3.1-8b-instant",
            "api_key": "k",
        }
    )
    assert settings.mode == SCAN_MODE_HYBRID
    assert settings.analyzer_model == "groq/llama-3.3-70b-versatile"
    assert settings.reporter_model == "groq/llama-3.1-8b-instant"


def test_resolve_scan_llm_settings_env_override(monkeypatch):
    monkeypatch.setenv("PRODGUARDIAN_SCAN_MODE", "hybrid")
    monkeypatch.setenv("PRODGUARDIAN_ANALYZER_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("PRODGUARDIAN_REPORTER_MODEL", "openai/gpt-4o-mini")
    settings = resolve_scan_llm_settings({"model": "gpt-3.5-turbo", "api_key": "k"})
    assert settings.mode == SCAN_MODE_HYBRID
    assert settings.analyzer_model == "openai/gpt-4o"
    assert settings.reporter_model == "openai/gpt-4o-mini"


def test_hybrid_prompts_include_presets_rules():
    presets = [{"name": "Secrets", "items": ["sk-"], "enabled": True}]
    rules = [
        {
            "name": "No secrets",
            "instruction": "Find hardcoded secrets",
            "preset_names": ["Secrets"],
            "enabled": True,
        }
    ]
    analyzer = build_analyzer_prompt([("app.py", "x=1")], presets, rules, "demo")
    reporter = build_reporter_prompt("notes", [[("app.py", "x=1")]], presets, rules, "demo")
    assert "Secrets" in analyzer
    assert "No secrets" in reporter
    assert "JSON array" in reporter


@patch("prodguardian.llm.ollama.prepare_ollama_model")
def test_prepare_scan_models_pulls_ollama_models(mock_prepare):
    mock_prepare.return_value = None
    settings = ScanLLMSettings(
        mode=SCAN_MODE_HYBRID,
        mono_model="gpt-3.5-turbo",
        analyzer_model="ollama/llama3.1:70b",
        reporter_model="ollama/llama3.2:3b",
        api_key="ollama",
        base_url="http://localhost:11434",
    )
    assert prepare_scan_models(settings) is None
    assert mock_prepare.call_count == 2


@patch("prodguardian.llm.codebase_scanner.ScanLLMRouter")
def test_hybrid_scanner_uses_analyzer_then_reporter(mock_router_cls, tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "main.py").write_text("API_KEY='secret'\n")

    mock_router = MagicMock()
    mock_router.budget_model.return_value = "groq/llama-3.3-70b-versatile"
    mock_router.analyze_chunk.return_value = "- Hardcoded API key in main.py"
    mock_router.report_findings.return_value = json.dumps(
        [
            {
                "rule_id": "LLM001",
                "severity": "CRITICAL",
                "file": "main.py",
                "line": 1,
                "message": "Hardcoded API key",
                "code_snippet": "API_KEY",
            }
        ]
    )
    mock_router_cls.return_value = mock_router

    settings = ScanLLMSettings(
        mode=SCAN_MODE_HYBRID,
        mono_model="gpt-3.5-turbo",
        analyzer_model="groq/llama-3.3-70b-versatile",
        reporter_model="groq/llama-3.1-8b-instant",
        api_key="test",
        base_url="",
    )
    scanner = CodebaseLLMScanner(
        project,
        get_presets(),
        get_rules(),
        scan_settings=settings,
        max_cost_usd=1.0,
        skip_test_dirs=False,
    )
    report = scanner.scan()

    assert mock_router.analyze_chunk.called
    assert mock_router.report_findings.called
    assert not mock_router.complete_mono.called
    assert len(report.issues) == 1