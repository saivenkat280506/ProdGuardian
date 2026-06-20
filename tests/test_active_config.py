from prodguardian.llm.active_config import (
    effective_cloud_base_url,
    is_ollama_base_url,
    normalize_llm_config,
    sync_llm_env,
)


def test_normalize_ollama_model():
    cfg = normalize_llm_config({"provider": "ollama", "model": "llama3.2", "api_key": "", "base_url": ""})
    assert cfg["provider"] == "ollama"
    assert cfg["model"] == "ollama/llama3.2"
    assert cfg["api_key"] == "ollama"
    assert cfg["base_url"]


def test_normalize_cloud_model():
    cfg = normalize_llm_config(
        {"provider": "api", "model": "gpt-4o-mini", "api_key": "sk-test", "base_url": "https://api.example.com"}
    )
    assert cfg["provider"] == "api"
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["api_key"] == "sk-test"
    assert cfg["base_url"] == "https://api.example.com"


def test_normalize_cloud_clears_stale_ollama_base_url():
    cfg = normalize_llm_config(
        {
            "provider": "api",
            "model": "groq/llama-3.1-8b-instant",
            "api_key": "gsk-test",
            "base_url": "http://localhost:11434",
        }
    )
    assert cfg["base_url"] == ""


def test_is_ollama_base_url():
    assert is_ollama_base_url("http://localhost:11434")
    assert is_ollama_base_url("http://127.0.0.1:11434/")
    assert not is_ollama_base_url("https://api.example.com")


def test_effective_cloud_base_url_ignores_ollama_host_for_groq():
    assert effective_cloud_base_url("groq", "http://localhost:11434") == ""
    assert effective_cloud_base_url("groq", "https://proxy.example.com") == "https://proxy.example.com"


def test_sync_llm_env_sets_process_vars(monkeypatch):
    monkeypatch.delenv("PRODGUARDIAN_MODEL", raising=False)
    monkeypatch.delenv("PRODGUARDIAN_API_KEY", raising=False)
    monkeypatch.delenv("PRODGUARDIAN_BASE_URL", raising=False)

    sync_llm_env(
        {
            "provider": "ollama",
            "model": "ollama/llama3.2",
            "api_key": "ollama",
            "base_url": "http://127.0.0.1:11434",
        }
    )

    import os

    assert os.environ["PRODGUARDIAN_MODEL"] == "ollama/llama3.2"
    assert os.environ["PRODGUARDIAN_API_KEY"] == "ollama"
    assert os.environ["PRODGUARDIAN_BASE_URL"] == "http://127.0.0.1:11434"