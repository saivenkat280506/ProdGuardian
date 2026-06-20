import pytest
from pathlib import Path
from prodguardian.scanner.ast_parser import parse_project
from prodguardian.scanner.rule_engine import run_rules
from prodguardian.scanner.rules.hardcoded_secrets import HardcodedSecretsRule
from prodguardian.scanner.rules.missing_env import MissingEnvVarRule
from prodguardian.scanner.rules.debug_endpoints import DebugEndpointsRule
from prodguardian.scanner.rules.sql_injection import SQLInjectionRule
from prodguardian.scanner.rules.unsafe_eval import UnsafeEvalRule

FIXTURES = Path(__file__).parent / "fixtures"


class TestASTParser:
    def test_parse_python_file(self):
        file = FIXTURES / "python_vuln" / "bad.py"
        ast_data = parse_project(file)
        assert ast_data is not None
        assert "tree" in ast_data
        assert "code" in ast_data
        assert "lines" in ast_data

    def test_parse_js_file(self):
        file = FIXTURES / "js_vuln" / "bad.js"
        ast_data = parse_project(file)
        assert ast_data is not None

    def test_parse_unsupported_file(self):
        file = FIXTURES / "python_vuln" / "bad.py"
        ast_data = parse_project(file)
        assert ast_data is not None


class TestHardcodedSecretsRule:
    def test_detects_api_key(self):
        rule = HardcodedSecretsRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert any("API key" in i["message"] for i in issues)

    def test_detects_password(self):
        rule = HardcodedSecretsRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert any("Password" in i["message"] for i in issues)

    def test_clean_file_no_issues(self):
        rule = HardcodedSecretsRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "good.py")
        issues = rule.check(ast_data)
        assert len(issues) == 0


class TestMissingEnvVarRule:
    def test_detects_environ_access(self):
        rule = MissingEnvVarRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert len(issues) > 0

    def test_clean_file_no_issues(self):
        rule = MissingEnvVarRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "good.py")
        issues = rule.check(ast_data)
        assert len(issues) == 0


class TestDebugEndpointsRule:
    def test_detects_debug_mode(self):
        rule = DebugEndpointsRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert any("debug" in i["message"].lower() for i in issues)

    def test_detects_debug_endpoint(self):
        rule = DebugEndpointsRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert any("debug" in i["message"].lower() for i in issues)


class TestSQLInjectionRule:
    def test_detects_sql_injection(self):
        rule = SQLInjectionRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert len(issues) > 0

    def test_clean_file_no_issues(self):
        rule = SQLInjectionRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "good.py")
        issues = rule.check(ast_data)
        assert len(issues) == 0


class TestUnsafeEvalRule:
    def test_detects_eval(self):
        rule = UnsafeEvalRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert any("eval()" in i["message"] for i in issues)

    def test_detects_exec(self):
        rule = UnsafeEvalRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert any("exec()" in i["message"] for i in issues)


class TestRuleEngine:
    def test_run_rules_on_vulnerable_file(self):
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = run_rules(ast_data)
        assert len(issues) > 0
        assert all("rule_id" in i for i in issues)
        assert all("severity" in i for i in issues)
        assert all("file" in i for i in issues)

    def test_run_rules_on_clean_file(self):
        ast_data = parse_project(FIXTURES / "python_vuln" / "good.py")
        issues = run_rules(ast_data)
        assert len(issues) == 0

    def test_run_rules_on_none(self):
        issues = run_rules(None)
        assert issues == []
