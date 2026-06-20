"""Single source of truth for the active LLM / Ollama model used by the backend."""

from __future__ import annotations

import os
from typing import Any

from prodguardian.llm.ollama import DEFAULT_OLLAMA_HOST, ollama_litellm_model

_OLLAMA_BASE_URLS = {
    DEFAULT_OLLAMA_HOST.rstrip("/").lower(),
    "http://localhost:11434",
    "http://127.0.0.1:11434",
}


def is_ollama_base_url(base_url: str) -> bool:
    """True when base_url points at a local Ollama daemon."""
    return base_url.rstrip("/").lower() in _OLLAMA_BASE_URLS


def effective_cloud_base_url(provider: str, base_url: str) -> str:
    """
    Return api_base for LiteLLM on cloud providers.

    Stale Ollama URLs saved after switching from local → cloud must not be sent.
    """
    if provider == "ollama":
        return base_url or DEFAULT_OLLAMA_HOST
    cleaned = base_url.strip()
    if not cleaned or is_ollama_base_url(cleaned):
        return ""
    return cleaned

ENV_MODEL = "PRODGUARDIAN_MODEL"
ENV_API_KEY = "PRODGUARDIAN_API_KEY"
ENV_BASE_URL = "PRODGUARDIAN_BASE_URL"
ENV_SCAN_MODE = "PRODGUARDIAN_SCAN_MODE"
ENV_ANALYZER_MODEL = "PRODGUARDIAN_ANALYZER_MODEL"
ENV_REPORTER_MODEL = "PRODGUARDIAN_REPORTER_MODEL"


def normalize_llm_config(raw: dict[str, Any]) -> dict[str, str]:
    """
    Canonicalize user choice so backend always uses exactly one provider + model.

    Ollama: model is always ``ollama/<name>``, api_key is ``ollama``, base_url set.
    Cloud: model/api_key/base_url from user input; ollama prefix stripped from provider.
    """
    provider = str(raw.get("provider", "api")).strip().lower()
    model = str(raw.get("model", "gpt-3.5-turbo")).strip()
    api_key = str(raw.get("api_key", "")).strip()
    base_url = str(raw.get("base_url", "")).strip()

    if model.startswith("ollama/"):
        provider = "ollama"

    if provider == "ollama":
        bare = model.removeprefix("ollama/")
        if not bare:
            bare = model
        return {
            "provider": "ollama",
            "model": ollama_litellm_model(bare),
            "api_key": "ollama",
            "base_url": base_url or DEFAULT_OLLAMA_HOST,
        }

    cloud_base = effective_cloud_base_url("api", base_url)

    return {
        "provider": "api",
        "model": model or "gpt-3.5-turbo",
        "api_key": api_key,
        "base_url": cloud_base,
    }


def sync_llm_env(config: dict[str, str]) -> None:
    """Push the active config into process env for subprocesses / litellm."""
    os.environ[ENV_MODEL] = config["model"]

    if config.get("api_key"):
        os.environ[ENV_API_KEY] = config["api_key"]
    else:
        os.environ.pop(ENV_API_KEY, None)

    if config.get("base_url"):
        os.environ[ENV_BASE_URL] = config["base_url"]
    else:
        os.environ.pop(ENV_BASE_URL, None)


def read_llm_from_disk() -> dict[str, str]:
    """Read authoritative LLM settings from ~/.prodguardian.toml (not stale env)."""
    from prodguardian.tui.settings_store import get_settings

    return normalize_llm_config(get_settings()["llm"])


def get_active_llm_config() -> dict[str, str]:
    """Config every backend path must use: scan, fix, explain, CLI."""
    return read_llm_from_disk()


def bootstrap_llm_from_disk() -> dict[str, str]:
    """Load disk config and sync env — call once at app/orchestrator startup."""
    config = read_llm_from_disk()
    sync_llm_env(config)
    return config


def is_llm_ready(config: dict[str, str] | None = None) -> bool:
    """True when scan/fix can run with the user's chosen provider."""
    cfg = config or get_active_llm_config()
    if cfg["provider"] == "ollama":
        return bool(cfg["model"].removeprefix("ollama/"))
    return bool(cfg.get("api_key"))


def get_scan_llm_settings():
    """Resolved Mono/Hybrid scan settings from disk + environment."""
    from prodguardian.llm.llm_router import resolve_scan_llm_settings
    from prodguardian.tui.settings_store import get_settings

    return resolve_scan_llm_settings(get_settings()["llm"])