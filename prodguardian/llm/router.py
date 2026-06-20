"""Backward-compatible LLM router — delegates to LiteLLMCompletionRouter."""

from prodguardian.llm.llm_router import LiteLLMCompletionRouter


class LLMRouter:
    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._router = LiteLLMCompletionRouter(
            model=model,
            api_key=api_key or "",
            base_url=base_url or "",
        )

    def complete(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> str:
        return self._router.complete(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )