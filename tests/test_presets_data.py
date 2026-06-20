from prodguardian.scan.presets_data import (
    BUILTIN_PRESET_TEMPLATES,
    BUILTIN_RULE_TEMPLATES,
    PRESET_CATEGORIES,
    build_llm_presets_context,
    get_preset_keywords,
    load_all_presets,
    load_all_rules,
)


def test_builtin_preset_count():
    assert len(BUILTIN_PRESET_TEMPLATES) >= 15


def test_builtin_rule_count():
    assert len(BUILTIN_RULE_TEMPLATES) >= 15


def test_all_presets_have_category_and_severity():
    for preset in BUILTIN_PRESET_TEMPLATES:
        assert preset.get("category") in PRESET_CATEGORIES
        assert preset.get("severity") in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert preset.get("items")


def test_get_preset_keywords_merges_patterns():
    preset = {"items": ["foo"], "patterns": ["bar"]}
    assert get_preset_keywords(preset) == ["foo", "bar"]


def test_load_all_presets_returns_defaults():
    presets = load_all_presets()
    names = {p["name"] for p in presets}
    assert "Hardcoded Secrets" in names
    assert "SQL Injection Patterns" in names


def test_load_all_rules_returns_defaults():
    rules = load_all_rules()
    names = {r["name"] for r in rules}
    assert "SQL injection prevention" in names


def test_build_llm_presets_context_groups_by_category():
    text = build_llm_presets_context(load_all_presets(), load_all_rules())
    assert "Production Guardrails" in text
    assert "[Secrets & Credentials]" in text
    assert "SQL injection prevention" in text
    assert "Linked presets:" in text