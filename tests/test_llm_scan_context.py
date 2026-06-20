"""Verify LLM scan context stays structured with expanded presets/rules."""

from pathlib import Path

from prodguardian.llm.codebase_scanner import build_analyzer_prompt, build_codebase_scan_prompt
from prodguardian.scan.presets_data import build_llm_presets_context, load_all_presets, load_all_rules
from prodguardian.tui.settings_store import get_presets, get_rules

FIXTURES = Path(__file__).parent / "fixtures" / "mixed_repo"


def test_guardrails_context_has_output_contract():
    text = build_llm_presets_context(load_all_presets(), load_all_rules())
    assert "Output contract" in text
    assert "JSON array" in text
    assert "static Audit" in text
    assert "[Recommended for Production]" in text


def test_guardrails_context_size_bounded():
    """Expanded presets should stay under a reasonable prompt budget."""
    text = build_llm_presets_context(get_presets(), get_rules())
    assert len(text) < 18_000
    assert text.count("Category:") >= 10


def test_mono_scan_prompt_on_fixture_chunk():
    backend = FIXTURES / "backend" / "api.py"
    content = backend.read_text(encoding="utf-8")
    prompt = build_codebase_scan_prompt(
        [("backend/api.py", content)],
        get_presets(),
        get_rules(),
        "mixed_repo",
    )
    assert "Return ONLY a JSON array" in prompt
    assert "static Audit" in prompt
    assert "backend/api.py" in prompt
    assert "Production Guardrails" in prompt


def test_hybrid_analyzer_prompt_format():
    prompt = build_analyzer_prompt(
        [("app.py", "print('x')")],
        get_presets(),
        get_rules(),
        "demo",
    )
    assert "file:line — finding" in prompt
    assert "Hybrid mode:" in build_llm_presets_context(get_presets(), get_rules())


def test_audit_issues_include_fix_hints():
    from prodguardian.production.auditor import ProductionAuditor

    auditor = ProductionAuditor(FIXTURES)
    issues = auditor.audit()
    prod019 = [i for i in issues if i.get("rule_id") == "PROD019"]
    if prod019:
        assert prod019[0].get("fix_hint")
    prod001 = [i for i in issues if i.get("rule_id") == "PROD001"]
    if prod001:
        assert prod001[0].get("generate_command") == "generate dockerfile"