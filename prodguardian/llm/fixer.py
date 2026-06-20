from pathlib import Path
from typing import Any, Optional

from .budget import TokenBudget, count_tokens
from .context import build_presets_context, build_prompt, extract_context
from .router import LLMRouter


class FixGenerator:
    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        max_tokens_per_fix: int = 800,
        max_cost_usd: float = 0.10,
    ):
        self.model = model
        self.max_tokens_per_fix = max_tokens_per_fix
        self.budget = TokenBudget(max_tokens=32000, max_cost_usd=max_cost_usd)
        self.router = None
        self.presets: list[dict[str, Any]] = []
        self.rules: list[dict[str, Any]] = []
        self._cache_dir = Path.home() / ".prodguardian_llm_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def _get_router(self) -> LLMRouter:
        if self.router is None:
            self.router = LLMRouter(self.model)
        return self.router

    def _get_cache_key(self, issue: dict[str, Any], mode: str) -> str:
        import hashlib
        raw = f"{mode}:{issue.get('rule_id', '')}:{issue.get('file', '')}:{issue.get('line', 0)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[str]:
        cache_file = self._cache_dir / f"{cache_key}.txt"
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")
        return None

    def _store_cache(self, cache_key: str, response: str):
        cache_file = self._cache_dir / f"{cache_key}.txt"
        cache_file.write_text(response, encoding="utf-8")

    def generate_fix(self, issue: dict[str, Any]) -> str:
        cache_key = self._get_cache_key(issue, "fix")
        cached = self._check_cache(cache_key)
        if cached:
            return f"[cached]\n{cached}"

        context = extract_context(issue)
        prompt = build_prompt(issue, context, self.presets, self.rules)
        prompt_tokens = count_tokens(prompt, self.model)

        can_proceed, reason = self.budget.can_proceed(prompt_tokens + self.max_tokens_per_fix, self.model)
        if not can_proceed:
            return f"Budget exceeded: {reason}"

        self.budget.consume(prompt_tokens)
        router = self._get_router()
        response = router.complete(prompt, max_tokens=self.max_tokens_per_fix)
        self._store_cache(cache_key, response)
        return response

    def explain(self, issue: dict[str, Any]) -> str:
        cache_key = self._get_cache_key(issue, "explain")
        cached = self._check_cache(cache_key)
        if cached:
            return f"[cached]\n{cached}"

        context = extract_context(issue, surrounding_lines=10)
        guardrails = build_presets_context(self.presets, self.rules)
        guardrails_block = f"{guardrails}\n\n" if guardrails else ""
        prompt = (
            f"Explain this issue concisely:\n\n{guardrails_block}"
            f"Issue: {issue.get('message', 'unknown')}\n"
            f"Rule: {issue.get('rule_id', 'unknown')}\n"
            f"Severity: {issue.get('severity', 'unknown')}\n"
            f"File: {issue.get('file', 'unknown')}, Line: {issue.get('line', 0)}\n\n"
            f"Code:\n{context}"
        )
        prompt_tokens = count_tokens(prompt, self.model)

        can_proceed, reason = self.budget.can_proceed(prompt_tokens + 300, self.model)
        if not can_proceed:
            return f"Budget exceeded: {reason}"

        self.budget.consume(prompt_tokens)
        router = self._get_router()
        response = router.complete(prompt, max_tokens=300)
        self._store_cache(cache_key, response)
        return response
