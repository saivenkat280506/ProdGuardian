"""
Scan LLM routing — Mono and Hybrid modes via LiteLLM.

Mono mode (default)
-------------------
One model handles every chunk: presets + rules + files → structured JSON findings.

Hybrid mode (advanced)
----------------------
1. Analyzer model reads each chunk with presets + rules → observations / summary notes.
2. Reporter model receives the combined summary + excerpt chunks + rules → final JSON.

Configuration is resolved from ~/.prodguardian.toml, then environment variables.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from prodguardian.llm.active_config import effective_cloud_base_url
from prodguardian.llm.ollama import DEFAULT_OLLAMA_HOST, ollama_litellm_model

logger = logging.getLogger(__name__)

SCAN_MODE_MONO = "mono"
SCAN_MODE_HYBRID = "hybrid"

ENV_SCAN_MODE = "PRODGUARDIAN_SCAN_MODE"
ENV_ANALYZER_MODEL = "PRODGUARDIAN_ANALYZER_MODEL"
ENV_REPORTER_MODEL = "PRODGUARDIAN_REPORTER_MODEL"

HYBRID_RECOMMENDED_PAIRS: list[dict[str, str]] = [
    {
        "label": "Groq 70B analyzer + 8B reporter",
        "analyzer": "groq/llama-3.3-70b-versatile",
        "reporter": "groq/llama-3.1-8b-instant",
    },
    {
        "label": "OpenAI GPT-4o mini analyzer + reporter",
        "analyzer": "openai/gpt-4o-mini",
        "reporter": "openai/gpt-4o-mini",
    },
    {
        "label": "Ollama 70B analyzer + 3B reporter (local)",
        "analyzer": "ollama/llama3.1:70b",
        "reporter": "ollama/llama3.2:3b",
    },
]

DEFAULT_ANALYZER_MODEL = "groq/llama-3.3-70b-versatile"
DEFAULT_REPORTER_MODEL = "groq/llama-3.1-8b-instant"

ProgressCallback = Callable[[str], None]

# Retries when the provider returns 429 / "rate limit" / "request too large".
MAX_RATE_LIMIT_RETRIES = 5


def _retry_wait_seconds(error_message: str, attempt: int) -> float:
    """Parse provider retry hint or use a safe backoff."""
    match = re.search(r"try again in\s+([\d.]+)\s*s", error_message, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 0.5
    return min(30.0, 8.0 * (attempt + 1))


def detect_provider_from_model(model: str) -> str:
    """Infer LiteLLM provider prefix from a model string."""
    model = model.strip()
    if model.startswith("ollama/"):
        return "ollama"
    if "/" in model:
        return model.split("/", 1)[0].lower()
    lower = model.lower()
    if lower.startswith("gpt-") or lower.startswith("o1") or lower.startswith("o3"):
        return "openai"
    if lower.startswith("claude-"):
        return "anthropic"
    if lower.startswith("gemini"):
        return "gemini"
    return "openai"


def normalize_model_string(model: str) -> str:
    """Normalize user model input for LiteLLM."""
    model = model.strip()
    if not model:
        return "gpt-3.5-turbo"
    if model.startswith("ollama/"):
        return model
    # Bare Ollama tags like llama3.2:3b (no provider prefix).
    if "/" not in model and ":" in model:
        return ollama_litellm_model(model)
    provider = detect_provider_from_model(model)
    if provider == "ollama":
        return ollama_litellm_model(model)
    return model


@dataclass
class ScanLLMSettings:
    """Resolved scan configuration used by CodebaseLLMScanner."""

    mode: str
    mono_model: str
    analyzer_model: str
    reporter_model: str
    api_key: str
    base_url: str

    @property
    def is_hybrid(self) -> bool:
        return self.mode == SCAN_MODE_HYBRID

    def models_in_use(self) -> list[str]:
        if self.is_hybrid:
            return [self.analyzer_model, self.reporter_model]
        return [self.mono_model]

    def describe(self) -> str:
        if self.is_hybrid:
            return (
                f"hybrid — analyzer={self.analyzer_model}, "
                f"reporter={self.reporter_model}"
            )
        return f"mono — {self.mono_model}"


def resolve_scan_llm_settings(raw_llm: dict[str, Any]) -> ScanLLMSettings:
    """
    Merge disk config + env vars into ScanLLMSettings.

    Backward compatible: missing scan_mode defaults to mono using ``model``.
    """
    from prodguardian.llm.active_config import ENV_API_KEY, ENV_BASE_URL, ENV_MODEL, normalize_llm_config

    normalized = normalize_llm_config(raw_llm)
    mode = (
        os.environ.get(ENV_SCAN_MODE)
        or str(raw_llm.get("scan_mode", SCAN_MODE_MONO)).strip().lower()
    )
    if mode not in (SCAN_MODE_MONO, SCAN_MODE_HYBRID):
        mode = SCAN_MODE_MONO

    mono_model = normalize_model_string(
        os.environ.get(ENV_MODEL) or str(raw_llm.get("model", normalized["model"]))
    )

    analyzer = normalize_model_string(
        os.environ.get(ENV_ANALYZER_MODEL)
        or str(raw_llm.get("analyzer_model", "")).strip()
        or DEFAULT_ANALYZER_MODEL
    )
    reporter = normalize_model_string(
        os.environ.get(ENV_REPORTER_MODEL)
        or str(raw_llm.get("reporter_model", "")).strip()
        or DEFAULT_REPORTER_MODEL
    )

    api_key = os.environ.get(ENV_API_KEY) or normalized["api_key"]
    provider = detect_provider_from_model(mono_model)
    raw_base = normalized.get("base_url", "") or os.environ.get(ENV_BASE_URL) or ""
    base_url = effective_cloud_base_url(provider, raw_base)

    if mode != SCAN_MODE_HYBRID:
        mode = SCAN_MODE_MONO
        analyzer = mono_model
        reporter = mono_model

    return ScanLLMSettings(
        mode=mode,
        mono_model=mono_model,
        analyzer_model=analyzer,
        reporter_model=reporter,
        api_key=api_key,
        base_url=base_url,
    )


class LiteLLMCompletionRouter:
    """Thin LiteLLM wrapper — shared by scan, fix, and explain paths."""

    def __init__(
        self,
        model: str,
        api_key: str = "",
        base_url: str = "",
        *,
        on_rate_limit_hit: Callable[[], None] | None = None,
    ):
        self.model = normalize_model_string(model)
        self.api_key = api_key
        self.base_url = base_url
        self.provider = detect_provider_from_model(self.model)
        self.api_calls = 0
        self._on_rate_limit_hit = on_rate_limit_hit

    def complete(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> str:
        try:
            from litellm import completion
        except ImportError as exc:
            logger.error("litellm is not installed")
            raise RuntimeError(
                "litellm is not installed. Run: pip install litellm"
            ) from exc

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if self.provider == "ollama":
            kwargs["api_key"] = self.api_key or "ollama"
            kwargs["api_base"] = self.base_url or DEFAULT_OLLAMA_HOST
        else:
            if not self.api_key:
                raise RuntimeError(
                    f"No API key configured for {self.model}. "
                    "Open Settings and set your Cloud API key."
                )
            kwargs["api_key"] = self.api_key
            api_base = effective_cloud_base_url(self.provider, self.base_url)
            if api_base:
                kwargs["api_base"] = api_base

        last_error: Exception | None = None
        for attempt in range(MAX_RATE_LIMIT_RETRIES):
            try:
                logger.info(
                    "Calling LLM API model=%s provider=%s max_tokens=%s attempt=%s",
                    self.model,
                    self.provider,
                    max_tokens,
                    attempt + 1,
                )
                response = completion(**kwargs)
                content = response.choices[0].message.content
                if not content or not str(content).strip():
                    raise RuntimeError(f"LLM returned an empty response for {self.model}")
                self.api_calls += 1
                return str(content)
            except RuntimeError:
                raise
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                is_rate_limit = "rate_limit" in message or "rate limit" in message
                is_too_large = "too large" in message or "request too large" in message
                if (is_rate_limit or is_too_large) and attempt < MAX_RATE_LIMIT_RETRIES - 1:
                    if is_rate_limit and self._on_rate_limit_hit is not None:
                        self._on_rate_limit_hit()
                    wait = _retry_wait_seconds(str(exc), attempt)
                    logger.warning(
                        "LLM rate limited for %s; retrying in %.1fs (%s/%s)",
                        self.model,
                        wait,
                        attempt + 1,
                        MAX_RATE_LIMIT_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                logger.warning("LiteLLM error for %s: %s", self.model, exc)
                if is_rate_limit or is_too_large:
                    raise RuntimeError(
                        f"LLM rate limit hit for {self.model}. "
                        f"ProdGuardian split the scan into smaller chunks — "
                        f"wait a minute and retry, or upgrade your Groq tier. "
                        f"Details: {exc}"
                    ) from exc
                raise RuntimeError(f"LLM API call failed for {self.model}: {exc}") from exc

        if last_error is not None:
            raise RuntimeError(f"LLM API call failed for {self.model}: {last_error}") from last_error
        raise RuntimeError(f"LLM API call failed for {self.model}")


class ScanLLMRouter:
    """
    Routes scan prompts to the correct model(s) for Mono or Hybrid mode.

    Mono: one router, same model every chunk.
    Hybrid: analyzer router per chunk, reporter router for final JSON.
    """

    def __init__(
        self,
        settings: ScanLLMSettings,
        *,
        on_rate_limit_hit: Callable[[], None] | None = None,
    ):
        self.settings = settings
        creds = {
            "api_key": settings.api_key,
            "base_url": settings.base_url,
            "on_rate_limit_hit": on_rate_limit_hit,
        }
        self._mono = LiteLLMCompletionRouter(settings.mono_model, **creds)
        self._analyzer = LiteLLMCompletionRouter(settings.analyzer_model, **creds)
        self._reporter = LiteLLMCompletionRouter(settings.reporter_model, **creds)

    def complete_mono(
        self,
        prompt: str,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> str:
        return self._mono.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def analyze_chunk(
        self,
        prompt: str,
        *,
        max_tokens: int = 900,
        temperature: float = 0.2,
    ) -> str:
        return self._analyzer.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def report_findings(
        self,
        prompt: str,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> str:
        return self._reporter.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def budget_model(self) -> str:
        """Model name used for token/cost estimation in the active mode."""
        if self.settings.is_hybrid:
            return self.settings.analyzer_model
        return self.settings.mono_model

    def api_calls_made(self) -> int:
        """Total successful LiteLLM completions in this scan session."""
        return (
            self._mono.api_calls
            + self._analyzer.api_calls
            + self._reporter.api_calls
        )


def prepare_scan_models(
    settings: ScanLLMSettings,
    on_progress: ProgressCallback | None = None,
) -> Optional[str]:
    """
    Ensure Ollama is running and pull any ollama/* models required for the scan.

    Returns a user-friendly error string, or None on success.
    """
    from prodguardian.llm.ollama import prepare_ollama_model

    ollama_models: list[str] = []
    for model in settings.models_in_use():
        if model.startswith("ollama/"):
            bare = model.removeprefix("ollama/")
            if bare and bare not in ollama_models:
                ollama_models.append(bare)

    if not ollama_models:
        return None

    for bare in ollama_models:
        if on_progress:
            on_progress(f"Preparing Ollama model {bare}...")
        error = prepare_ollama_model(bare, on_progress=on_progress)
        if error:
            return error
    return None