import pytest

from prodguardian.llm.llm_router import LiteLLMCompletionRouter, resolve_scan_llm_settings


def test_resolve_scan_settings_clears_ollama_base_for_groq(monkeypatch):
    monkeypatch.delenv("PRODGUARDIAN_BASE_URL", raising=False)
    monkeypatch.delenv("PRODGUARDIAN_API_KEY", raising=False)
    monkeypatch.delenv("PRODGUARDIAN_MODEL", raising=False)
    settings = resolve_scan_llm_settings(
        {
            "provider": "api",
            "model": "groq/llama-3.1-8b-instant",
            "api_key": "gsk-test",
            "base_url": "http://localhost:11434",
            "scan_mode": "mono",
        }
    )
    assert settings.base_url == ""


def test_lite_llm_router_requires_api_key_for_cloud():
    router = LiteLLMCompletionRouter("groq/llama-3.1-8b-instant", api_key="", base_url="")
    with pytest.raises(RuntimeError, match="No API key configured"):
        router.complete("test prompt", max_tokens=10)