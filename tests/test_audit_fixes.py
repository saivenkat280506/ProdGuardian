from prodguardian.production.audit_fixes import AUDIT_FIX_HINTS, enrich_audit_issue


def test_all_prod_rules_have_hints():
    for rule_id in (
        "PROD009", "PROD012", "PROD014", "PROD018", "PROD019",
    ):
        assert rule_id in AUDIT_FIX_HINTS
        assert AUDIT_FIX_HINTS[rule_id].get("fix_hint")


def test_enrich_audit_issue_attaches_metadata():
    raw = {
        "rule_id": "PROD019",
        "severity": "HIGH",
        "file": "app.py",
        "line": 0,
        "message": "Wildcard CORS",
        "code_snippet": "",
    }
    enriched = enrich_audit_issue(raw)
    assert "fix_hint" in enriched
    assert "allowlist" in enriched["fix_hint"].lower() or "FRONTEND_URL" in enriched["fix_hint"]