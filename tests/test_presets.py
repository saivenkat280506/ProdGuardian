from pathlib import Path

from prodguardian.llm.context import build_presets_context, build_prompt
from prodguardian.scan.preset_scanner import scan_file_presets
from prodguardian.scan.presets_data import BUILTIN_PRESET_TEMPLATES


def test_scan_file_presets_finds_keyword():
    presets = [
        {
            "name": "Debug Code",
            "items": ["console.log"],
            "enabled": True,
        }
    ]
    content = "function run() {\n  console.log('debug');\n}\n"
    issues = scan_file_presets(Path("app.js"), content, presets)

    assert len(issues) == 1
    assert issues[0]["rule_id"] == "PRESET001"
    assert issues[0]["line"] == 2
    assert "console.log" in issues[0]["message"]


def test_build_presets_context_includes_rules():
    presets = BUILTIN_PRESET_TEMPLATES[:1]
    rules = [
        {
            "name": "No secrets",
            "instruction": "Flag hardcoded API keys",
            "preset_names": ["Hardcoded Secrets"],
            "enabled": True,
        }
    ]
    text = build_presets_context(presets, rules)

    assert "Hardcoded Secrets" in text
    assert "No secrets" in text
    assert "Flag hardcoded API keys" in text


def test_build_prompt_injects_presets():
    issue = {"message": "test", "rule_id": "PRESET001", "severity": "HIGH", "file": "a.py", "line": 1}
    prompt = build_prompt(issue, ">>> bad()", presets=BUILTIN_PRESET_TEMPLATES[:1], rules=[])

    assert "Production Guardrails" in prompt or "Production presets" in prompt
    assert "Hardcoded Secrets" in prompt