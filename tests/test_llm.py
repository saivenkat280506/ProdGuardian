import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from prodguardian.llm.router import LLMRouter
from prodguardian.llm.budget import TokenBudget, count_tokens, estimate_cost
from prodguardian.llm.context import extract_context, build_prompt
from prodguardian.llm.fixer import FixGenerator

FIXTURES = Path(__file__).parent / "fixtures"


class TestTokenBudget:
    def test_count_tokens_basic(self):
        tokens = count_tokens("Hello world")
        assert tokens > 0

    def test_estimate_cost(self):
        cost = estimate_cost(1000, "gpt-3.5-turbo")
        assert cost > 0
        assert cost < 0.01

    def test_budget_can_proceed(self):
        budget = TokenBudget(max_tokens=1000, max_cost_usd=1.0)
        can, msg = budget.can_proceed(500, "gpt-3.5-turbo")
        assert can

    def test_budget_exceeded(self):
        budget = TokenBudget(max_tokens=100, max_cost_usd=0.001)
        can, msg = budget.can_proceed(200, "gpt-3.5-turbo")
        assert not can

    def test_budget_consume(self):
        budget = TokenBudget(max_tokens=1000)
        budget.consume(100)
        assert budget.used_tokens == 100


class TestLLMRouter:
    def test_missing_api_key(self):
        # Router defers key requirement to litellm / call time (supports env or explicit)
        with patch.dict("os.environ", {}, clear=True):
            router = LLMRouter(model="gpt-3.5-turbo")
            assert router.model == "gpt-3.5-turbo"
            assert router.api_key is None

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_router_init(self):
        router = LLMRouter(model="gpt-3.5-turbo")
        assert router.model == "gpt-3.5-turbo"


class TestContext:
    def test_extract_context(self):
        issue = {
            "file": str(FIXTURES / "python_vuln" / "bad.py"),
            "line": 2,
        }
        context = extract_context(issue, surrounding_lines=5)
        assert len(context) > 0
        assert ">>>" in context

    def test_extract_context_missing_file(self):
        issue = {"file": "/nonexistent/file.py", "line": 1}
        context = extract_context(issue)
        assert context == ""

    def test_build_prompt(self):
        issue = {
            "rule_id": "SEC001",
            "severity": "CRITICAL",
            "file": "test.py",
            "line": 10,
            "message": "Hardcoded API key found",
        }
        context = "API_KEY = 'sk-1234567890'"
        prompt = build_prompt(issue, context)
        assert "SEC001" in prompt
        assert "Hardcoded API key found" in prompt
        assert ">>>" in prompt


class TestFixGenerator:
    def test_fix_generator_init(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            gen = FixGenerator(model="gpt-3.5-turbo")
            assert gen.model == "gpt-3.5-turbo"

    def test_budget_exceeded(self):
        import shutil
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            gen = FixGenerator(model="gpt-3.5-turbo", max_cost_usd=0.0)
            # Clear cache to avoid stale results
            if gen._cache_dir.exists():
                shutil.rmtree(gen._cache_dir)
            gen._cache_dir.mkdir(exist_ok=True)
            issue = {
                "rule_id": "SEC002",
                "file": str(FIXTURES / "python_vuln" / "good.py"),
                "line": 1,
                "message": "Test issue",
                "severity": "MEDIUM",
            }
            result = gen.generate_fix(issue)
            assert "Budget exceeded" in result

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_explain_returns_string(self):
        gen = FixGenerator(model="gpt-3.5-turbo", max_cost_usd=0.0)
        issue = {
            "rule_id": "SEC001",
            "file": str(FIXTURES / "python_vuln" / "bad.py"),
            "line": 2,
            "message": "Hardcoded API key",
            "severity": "CRITICAL",
        }
        result = gen.explain(issue)
        assert isinstance(result, str)
